"""The gdocs agent and its event forwarder.

This backend serves ONE hexgate agent — ``docs_agent`` — over the HexKit
contract. Two things make it the "gates" demo:

1. **Its tools come from an MCP server it doesn't own.** The agent connects to a
   fake Google Docs MCP server (spawned over stdio by the app lifespan) and
   inherits all six of its tools under the ``mcp-gdocs-*`` namespace. We gate
   them; we don't edit them.

2. **Its policy lives on the hexgate platform, not here.** The agent is created
   with ``bind_policy=True`` + ``name="docs_agent"``, so hexgate fetches the
   policy for ``docs_agent`` from the platform (``HEXGATE_API_URL`` with
   ``HEXGATE_API_KEY``) and hot-reloads it on every run. Edit the policy in the
   dashboard's **Policies** tab and the next message here reflects it — no
   redeploy. A blocked call surfaces as a hexgate ``error`` event, which the
   proxy's ``HexgateTranslator`` renders in the tool-calls widget.

The caller's HexKit role (``context.user.role`` — analyst / editor / admin)
drives which rules apply, via ``async with hexgate.User(role=...)``.

BYOK: the OpenAI key is never sent by HexKit. It's read from this process's env
(``OPENAI_API_KEY``) or handed in-memory to ``POST /byok`` (the demo notebook
posts it when the visitor pastes their key). It lives only in this throwaway
process's memory and is never persisted or logged.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from typing import Any

_DEFAULT_MODEL = os.getenv("HEXGATE_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = (
    "You are a Google Docs assistant for the team. You can search, read, create, "
    "share, export, and delete docs by calling the gdocs tools — always use a "
    "tool rather than guessing. Some actions may be blocked by policy depending "
    "on the user's role; if a tool call is denied, tell the user plainly what was "
    "blocked and why, and suggest an allowed alternative."
)

# Set by the app lifespan (see app.py) once the MCP toolset is connected: the
# live LangChain tools for the fake Google Docs server. None until then.
_mcp_tools: list[Any] | None = None

# BYOK: the visitor's OpenAI key, handed to this process in-memory via the
# POST /byok endpoint (the demo notebook posts it). Never written to disk.
_runtime_openai_key: str | None = None


def set_mcp_tools(tools: list[Any]) -> None:
    """Called by the app lifespan with the connected MCP toolset's tools."""
    global _mcp_tools
    _mcp_tools = tools


def set_openai_key(key: str | None) -> None:
    """Store the visitor's OpenAI key in process memory (BYOK). Never persisted."""
    global _runtime_openai_key
    _runtime_openai_key = (key or "").strip() or None


def _resolve_openai_key() -> str | None:
    """BYOK: this process's env, else the in-memory key posted to /byok."""
    return os.getenv("OPENAI_API_KEY") or _runtime_openai_key


# Built agents cached by (model, api_key) — no per-conversation state (full
# history is resent each turn), so one build is reused. Keyed on the OpenAI key
# so rotating it rebuilds. Memory-only; never persisted.
_agent_cache: dict[tuple[str, str], tuple[Any, Any]] = {}


def _get_agent(api_key: str) -> tuple[Any, Any]:
    """Return a cached (agent, handler), building + platform-binding on miss.

    ``create_agent(bind_policy=True, name="docs_agent")`` fetches the
    ``docs_agent`` policy from the platform at build time and attaches a refresh
    source, so the returned agent is already gated and hot-reloads per run.
    """
    cache_key = (_DEFAULT_MODEL, api_key)
    cached = _agent_cache.get(cache_key)
    if cached is not None:
        return cached

    if _mcp_tools is None:
        raise RuntimeError(
            "MCP toolset not connected — the gdocs server failed to start (see the app lifespan)."
        )

    # Imported lazily: hexgate pulls in heavy deps at import, so the /agents
    # roster stays cheap and we pay it only when a run needs the SDK.
    from hexgate import create_agent
    from langchain_openai import ChatOpenAI

    model = ChatOpenAI(model=_DEFAULT_MODEL, api_key=api_key, temperature=0)
    built = create_agent(
        model=model,
        tools=_mcp_tools,
        system_prompt=SYSTEM_PROMPT,
        name="docs_agent",  # the policy lookup key on the platform
        bind_policy=True,  # fetch + enforce the platform policy, hot-reloaded
    )
    _agent_cache[cache_key] = built
    return built


def _messages_with_files(input: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    """Forward the transcript, inlining any attached files as a system preface."""
    messages = list((input or {}).get("messages") or [])
    files = (context or {}).get("files") or []
    if not files:
        return messages
    listing = "\n\n".join(
        f"### {f.get('name')} ({f.get('mime')})\n{f.get('content') or '[binary file omitted]'}"
        for f in files
    )
    preface = {"role": "system", "content": f"Attached files:\n\n{listing}"}
    return [preface, *messages]


async def run_gdocs_agent(
    *, input: dict[str, Any], context: dict[str, Any], cancel: asyncio.Event
) -> AsyncIterator[dict]:
    """Stream one run as hexgate-native events (JSON-projected dicts).

    Yields each ``hexgate.StreamEvent`` as ``model_dump(mode="json")`` — the
    shape the proxy's HexgateTranslator reads. The caller tags each frame with
    ``framework: "hexgate"``.
    """
    api_key = _resolve_openai_key()
    if not api_key:
        yield {
            "event_type": "error",
            "message": (
                "No OpenAI API key available. Paste your key in the demo "
                "notebook (or set OPENAI_API_KEY in this backend's env)."
            ),
        }
        return

    from hexgate import User
    from hexgate.agents.factory import stream_agent

    try:
        # Build + platform-bind off the event loop: create_agent(bind_policy=True)
        # makes a synchronous HTTP round-trip to the platform (first call per key).
        agent, handler = await asyncio.to_thread(_get_agent, api_key)
    except Exception as exc:  # noqa: BLE001 — surface as a hexgate error event
        yield {"event_type": "error", "message": str(exc)}
        return

    messages = _messages_with_files(input, context)

    # Bind the run to the HexKit caller's identity — hexgate reads this
    # ContextVar to resolve the role's rules from the platform policy. No user
    # block = unscoped (falls through to the policy's fail-closed default).
    caller = (context or {}).get("user") or {}
    user_id = caller.get("id")
    role = caller.get("role")

    if user_id is None:
        async for event in stream_agent(agent, handler, {"messages": messages}):
            if cancel.is_set():
                return
            yield event.model_dump(mode="json")
        return

    async with User(user_id=user_id, role=role):
        async for event in stream_agent(agent, handler, {"messages": messages}):
            if cancel.is_set():
                return
            yield event.model_dump(mode="json")
