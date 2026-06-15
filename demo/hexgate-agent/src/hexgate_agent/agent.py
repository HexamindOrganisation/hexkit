"""The hexgate-wrapped agent and its event forwarder.

Two things make this backend interesting:

1. **What it forwards.** A hexgate agent exposes a normalized event stream via
   ``hexgate.stream_agent(...)`` — hexgate's own unified schema (``run_start`` /
   ``block_delta`` / ``tool_start`` / ...). We do **not** reshape those events
   into HexaUI's minimal `native` vocabulary; we forward them verbatim, tagged
   ``framework: "hexgate"``, and the proxy's ``HexgateTranslator`` maps them
   onto the rich internal schema. That round-trip is the whole point: it
   proves the two products' "same events" decision actually holds on the wire.

2. **The user identity it carries.** When the HexUI proxy sends
   ``context.user = {id, name, role}`` (CONTRACT.md §5), this backend opens an
   ``async with hexgate.User(user_id=..., role=...)`` block around the run.
   That ContextVar drives:

   - per-tool policy decisions (``enforce_policy(role, tool, args)``);
   - per-request biscuit attenuation by ``HexgateClient``;
   - audit events POSTed to the hexgate cloud, tagged with the HexUI user.

   To see those audit events on the cloud dashboard, set ``HEXGATE_KEY`` in
   this process's env (it's the dev/admin key — biscuits attenuate per request
   to scope back down to the HexUI user).

Wrapping vs. enforcement: ``create_agent`` already returns a hexgate-wrapped
agent (the runtime wrap whose event stream we test here). Policy enforcement is
a separate hexgate concern — add ``agent = agent.enforce_policy("policy.yaml")``
(see the SDK's examples/) once you want denials to flow through too; a blocked
tool surfaces as a hexgate ``error`` event, which the translator already
handles.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from langchain_core.tools import tool

# CHANGE ME (1/3): the model. Read from this backend's env (HEXGATE_MODEL),
# defaulting to gpt-4o-mini.
_DEFAULT_MODEL = os.getenv("HEXGATE_MODEL", "gpt-4o-mini")

# CHANGE ME (2/3): the system prompt. The nudge to call the tool makes the
# tool_start / tool_end path easy to observe end-to-end.
SYSTEM_PROMPT = (
    "You are Hexgate Guard, a concise assistant running inside the hexgate "
    "secure runtime. When the user asks for the current date or time, call the "
    "get_server_time tool rather than guessing."
)


# CHANGE ME (3/3): your tools. One deterministic tool so a run reliably exercises
# the tool_start -> tool_end event path through the hexgate translator.
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


# Built agents cached by (model, api_key). Built lazily on first use (not at
# import) and reused, since the agent holds no per-conversation state (full
# history is resent each turn, checkpointer=None). Keyed on the api_key so that
# rotating OPENAI_API_KEY in the env rebuilds against the new one. Memory-only —
# never persisted or logged; the key already lives inside the ChatOpenAI client
# regardless. Concurrent cold-cache builds just race harmlessly (last write
# wins, both results valid), so no lock is needed.
_agent_cache: dict[tuple[str, str], tuple[Any, Any]] = {}


def _get_agent(api_key: str) -> tuple[Any, Any]:
    """Return a cached (HexgateAgent, handler) for this key, building on miss."""
    cache_key = (_DEFAULT_MODEL, api_key)
    cached = _agent_cache.get(cache_key)
    if cached is not None:
        return cached

    # Imported lazily: hexgate pulls in heavy optional deps at import time, so
    # we keep module import (and the /agents roster) cheap and pay it only when
    # a run actually needs the SDK.
    from hexgate import create_agent
    from langchain_openai import ChatOpenAI

    model = ChatOpenAI(model=_DEFAULT_MODEL, api_key=api_key, temperature=0)
    built = create_agent(
        model=model,
        tools=[get_server_time],
        system_prompt=SYSTEM_PROMPT,
        name="hexgate-guard",
    )
    _agent_cache[cache_key] = built
    return built


async def run_hexgate_agent(
    *, input: dict[str, Any], context: dict[str, Any], cancel: asyncio.Event
) -> AsyncIterator[dict]:
    """Stream one run as hexgate-native events (JSON-projected dicts).

    Yields each ``hexgate.StreamEvent`` as ``model_dump(mode="json")`` — the
    exact shape the proxy's HexgateTranslator reads. The caller tags every
    frame with ``framework: "hexgate"``.
    """
    # The OpenAI key comes from this backend's own environment — HexUI does not
    # send provider keys. Read it per run; never persist or log it.
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # A hexgate-shaped error event — the translator maps it to an error.
        yield {
            "event_type": "error",
            "message": "No OpenAI API key available. Set OPENAI_API_KEY in this backend's environment.",
        }
        return

    # Built once and cached (see _get_agent); the env key scopes the cache
    # entry. stream_agent is imported lazily for the same reason as the SDK
    # imports inside _get_agent.
    from hexgate import User
    from hexgate.agents.factory import stream_agent

    agent, handler = _get_agent(api_key)
    messages = _messages_with_files(input, context)

    # Bind the run to the HexUI caller's identity. hexgate reads the ContextVar
    # set by `async with User(...)` for policy decisions, biscuit attenuation,
    # and audit emission. Missing user block = no scoping (the SDK still runs;
    # decisions just won't be tagged with a user).
    caller = (context or {}).get("user") or {}
    user_id = caller.get("id")
    role = caller.get("role")

    if user_id is None:
        # No caller identity — run unscoped. Useful for local "python -m" runs
        # and for backwards compat with proxies that don't yet send `user`.
        async for event in stream_agent(agent, handler, {"messages": messages}):
            if cancel.is_set():
                return
            yield event.model_dump(mode="json")
        return

    async with User(user_id=user_id, role=role):
        async for event in stream_agent(agent, handler, {"messages": messages}):
            if cancel.is_set():
                return  # stop producing; the proxy persists the partial text
            yield event.model_dump(mode="json")
