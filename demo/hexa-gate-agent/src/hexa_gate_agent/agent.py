"""The fortify-wrapped agent and its event forwarder.

The interesting part of this backend is *what it forwards*. A fortify agent
exposes a normalized event stream via ``fortify.stream_agent(...)`` — fortify's
own unified schema (``run_start`` / ``block_delta`` / ``tool_start`` / ...). We
do **not** reshape those events into HexaUI's minimal `native` vocabulary; we
forward them verbatim, tagged ``framework: "fortify"``, and the proxy's
``FortifyTranslator`` maps them onto the rich internal schema. That round-trip
is the whole point: it proves the two products' "same events" decision actually
holds on the wire.

Wrapping vs. enforcement: ``create_agent`` already returns a ``FortifyAgent``
(the runtime wrap whose event stream we test here). Policy enforcement is a
separate fortify concern — add ``agent = agent.enforce_policy("policy.yaml")``
(see the SDK's examples/) once you want denials to flow through too; a blocked
tool surfaces as a fortify ``error`` event, which the translator already
handles.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from langchain_core.tools import tool

# CHANGE ME (1/3): the model. Read per-run from the user's forwarded key; falls
# back to the process env for a standalone `python -m hexa_gate_agent` run.
_DEFAULT_MODEL = os.getenv("FORTIFY_MODEL", "gpt-4o-mini")

# CHANGE ME (2/3): the system prompt. The nudge to call the tool makes the
# tool_start / tool_end path easy to observe end-to-end.
SYSTEM_PROMPT = (
    "You are Fortify Guard, a concise assistant running inside the fortify "
    "secure runtime. When the user asks for the current date or time, call the "
    "get_server_time tool rather than guessing."
)


# CHANGE ME (3/3): your tools. One deterministic tool so a run reliably exercises
# the tool_start -> tool_end event path through the fortify translator.
@tool
def get_server_time(timezone_name: str = "UTC") -> str:
    """Return the current server time as an ISO-8601 string.

    Call this whenever the user asks what time or date it is.
    """
    # `timezone_name` is accepted for a realistic tool signature; this stub
    # always answers in UTC.
    _ = timezone_name
    return datetime.now(UTC).isoformat()


def _messages_with_files(
    input: dict[str, Any], context: dict[str, Any]
) -> list[dict[str, Any]]:
    """Forward the chat transcript, inlining any attached files as context.

    `context.files[*].content` is decoded text for text mimes and None for
    binary (the proxy fetches/decodes; see CONTRACT.md §5). We prepend a single
    system message so the model can read them.
    """
    messages = list((input or {}).get("messages") or [])
    files = (context or {}).get("files") or []
    if not files:
        return messages
    listing = "\n\n".join(
        f"### {f.get('name')} ({f.get('mime')})\n"
        f"{f.get('content') or '[binary file omitted]'}"
        for f in files
    )
    preface = {"role": "system", "content": f"Attached files:\n\n{listing}"}
    return [preface, *messages]


# Built agents cached by (model, api_key). The user's key arrives per-run (not
# at startup), so we can't build at import — but we can build once on first use
# and reuse it, since the agent holds no per-conversation state (full history is
# resent each turn, checkpointer=None). Keyed on the api_key, not merely
# built-once, so rotating the key in the UI rebuilds against the new one.
# Memory-only — never persisted or logged; the key already lives inside the
# ChatOpenAI client regardless. Concurrent cold-cache builds just race
# harmlessly (last write wins, both results valid), so no lock is needed.
_agent_cache: dict[tuple[str, str], tuple[Any, Any]] = {}


def _get_agent(api_key: str) -> tuple[Any, Any]:
    """Return a cached (FortifyAgent, handler) for this key, building on miss."""
    cache_key = (_DEFAULT_MODEL, api_key)
    cached = _agent_cache.get(cache_key)
    if cached is not None:
        return cached

    # Imported lazily: fortify pulls in heavy optional deps at import time, so we
    # keep module import (and the /agents roster) cheap and pay it only when a
    # run actually needs the SDK.
    from fortify import create_agent
    from langchain_openai import ChatOpenAI

    model = ChatOpenAI(model=_DEFAULT_MODEL, api_key=api_key, temperature=0)
    built = create_agent(
        model=model,
        tools=[get_server_time],
        system_prompt=SYSTEM_PROMPT,
        name="fortify-guard",
    )
    _agent_cache[cache_key] = built
    return built


async def run_fortify_agent(
    *, input: dict[str, Any], context: dict[str, Any], cancel: asyncio.Event
) -> AsyncIterator[dict]:
    """Stream one run as fortify-native events (JSON-projected dicts).

    Yields each ``fortify.StreamEvent`` as ``model_dump(mode="json")`` — the
    exact shape the proxy's FortifyTranslator reads. The caller tags every
    frame with ``framework: "fortify"``.
    """
    # context.credentials holds the user's decrypted secrets, flat
    # `{provider}_api_key`. Use them only for this run; never persist or log.
    creds = (context or {}).get("credentials") or {}
    api_key = creds.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        # A fortify-shaped error event — the translator maps it to an error.
        yield {
            "event_type": "error",
            "message": (
                "No OpenAI API key available. Add one in the UI (it arrives in "
                "context.credentials.openai_api_key) or set OPENAI_API_KEY."
            ),
        }
        return

    # Built once and cached (see _get_agent); the user's key scopes the cache
    # entry. stream_agent is imported lazily for the same reason as the SDK
    # imports inside _get_agent.
    from fortify.agents.factory import stream_agent

    agent, handler = _get_agent(api_key)
    messages = _messages_with_files(input, context)
    async for event in stream_agent(agent, handler, {"messages": messages}):
        if cancel.is_set():
            return  # stop producing; the proxy persists the partial text
        yield event.model_dump(mode="json")
