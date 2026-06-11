"""OpenAI Agents SDK → HexaUI contract bridge (write once per framework).

Turns any ``agents.Agent``'s native event stream into the framework-tagged
native events the proxy's ``OpenAIAgentsTranslator`` consumes. It is
**agent-agnostic**: :class:`OpenAIAgentsAgent` takes a *streamer* — an async
callable ``(input) -> AsyncIterator`` of SDK ``stream_events()`` items — and
projects each event onto the wire shapes. Which streamer (e.g.
``healthcare_agent.run`` vs a ``run_as`` partial) and which role are decided by
``select.py``; the agent and its streamers live in ``healthcare_agent.py``.

The proxy synthesizes the run envelope, sequence numbers, and block lifecycle;
this bridge only forwards native events.

Also hosts :func:`hexgate_api_key` — the one bit of HexGate infra (resolving the
platform key from env / ``.env``), kept here so the agent file stays pure SDK.
"""

from __future__ import annotations

import logging
import os
from typing import Any, AsyncIterator, Callable

from agents import set_default_openai_key

from .. import protocol

logger = logging.getLogger("agent_server.openai_agents")

# A streamer yields one run's native ``stream_events()`` items for some input.
Streamer = Callable[[Any], AsyncIterator[Any]]


def hexgate_api_key() -> str | None:
    """Resolve the HexGate platform key without the launcher having to set it.

    Priority: ``HEXGATE_KEY`` in the env → a ``.env`` at ``HEXGATE_ENV_FILE`` →
    the hexgate checkout's own ``.env`` (auto-discovered from the installed
    editable ``hexgate`` package). The demo keeps the key in the hexgate repo's
    ``.env``, so the agent works under ``run-backends.sh`` without anyone having
    to ``source`` it first. This is the HexGate *platform* key — separate from
    the per-run OpenAI key forwarded in ``context.credentials``.
    """
    key = os.getenv("HEXGATE_KEY")
    if key:
        return key
    try:
        from dotenv import dotenv_values
    except ImportError:
        return None
    env_file = os.getenv("HEXGATE_ENV_FILE")
    if not env_file:
        try:
            import hexgate
            from pathlib import Path

            env_file = str(Path(hexgate.__file__).resolve().parent.parent / ".env")
        except Exception:  # noqa: BLE001 — discovery is best-effort
            return None
    try:
        return dotenv_values(env_file).get("HEXGATE_KEY")
    except Exception:  # noqa: BLE001
        return None


def _agent_input(input: dict[str, Any]) -> Any:
    """Shape HexaUI's ``{"messages": [...]}`` into SDK input.

    The SDK accepts a transcript (list of role/content items) or a string; we
    pass the full messages list so multi-turn context is preserved, falling back
    to the last user message if the shape is unexpected.
    """
    messages = (input or {}).get("messages")
    if isinstance(messages, list) and messages:
        return messages
    return protocol.last_user_text(input)


def _project(ev: Any, names: dict[str, str]) -> dict | None:
    """Map one ``stream_events()`` item to a native JSON event (or None to drop).

    ``names`` carries call_id -> tool_name across events so the tool_output
    frame can label itself (the SDK's output raw_item omits the name).
    """
    etype = getattr(ev, "type", None)

    # Streamed assistant text.
    if etype == "raw_response_event":
        data = getattr(ev, "data", None)
        if getattr(data, "type", None) == "response.output_text.delta":
            delta = getattr(data, "delta", "") or ""
            if delta:
                return {
                    "type": "raw_response",
                    "data": {"type": "response.output_text.delta", "delta": delta},
                }
        return None

    # Tool calls + the message-finalized marker.
    if etype == "run_item_stream_event":
        name = getattr(ev, "name", None)
        item = getattr(ev, "item", None)
        raw = getattr(item, "raw_item", None)

        if name == "tool_called":
            call_id = getattr(raw, "call_id", None) or getattr(raw, "id", "") or ""
            tool_name = getattr(raw, "name", "tool") or "tool"
            arguments = getattr(raw, "arguments", "") or "{}"  # JSON string; proxy parses
            names[call_id] = tool_name
            return {
                "type": "run_item",
                "name": "tool_called",
                "item": {
                    "raw_item": {
                        "call_id": call_id,
                        "name": tool_name,
                        "arguments": arguments,
                    }
                },
            }

        if name == "tool_output":
            # raw_item here is a dict (function_call_output): {"call_id", "output", ...}
            call_id = raw.get("call_id", "") if isinstance(raw, dict) else getattr(raw, "call_id", "")
            return {
                "type": "run_item",
                "name": "tool_output",
                "item": {
                    "raw_item": {"call_id": call_id, "name": names.get(call_id, "tool")},
                    "output": getattr(item, "output", None),
                },
            }

        if name == "message_output_created":
            # The translator just closes the open text block here; content is
            # already streamed via raw_response deltas.
            return {
                "type": "run_item",
                "name": "message_output_created",
                "item": {"raw_item": {"content": []}},
            }

    # agent_updated / handoffs / mcp / reasoning items: ignored (parity with the
    # translator, which drops them).
    return None


class OpenAIAgentsAgent:
    """HexaUI contract agent for any OpenAI Agents SDK agent.

    Drives a *streamer* (e.g. ``healthcare_agent.run`` or a ``run_as`` partial)
    and forwards each SDK event as a framework-tagged native frame. Reusable for
    any ``agents.Agent`` — the agent itself, and whether HexGate wraps it, are
    decided by the caller that builds the streamer (see ``select.py``).
    """

    framework = "openai-agents"

    def __init__(self, streamer: Streamer) -> None:
        self._streamer = streamer

    async def run(
        self, *, input: dict[str, Any], context: dict[str, Any]
    ) -> AsyncIterator[dict]:
        api_key = ((context or {}).get("credentials") or {}).get("openai_api_key")
        if not api_key:
            yield protocol.error(
                "No OpenAI API key available. Add one in Settings (provider "
                "OpenAI) — it arrives per-run in context.credentials.openai_api_key."
            )
            return

        # Per-run model key; scope to this run, never persist/log. (Process-
        # global is fine for the single-user demo; a multi-tenant deploy would
        # pass a per-run AsyncOpenAI client.) The HexGate platform key is
        # separate — the streamer (run_as) carries it.
        set_default_openai_key(api_key)

        names: dict[str, str] = {}
        try:
            async for ev in self._streamer(_agent_input(input)):
                frame = _project(ev, names)
                if frame is not None:
                    yield frame
        except Exception as e:  # noqa: BLE001 — degrade to a visible error event
            logger.exception("openai-agents run failed")
            yield protocol.error(f"agent failed: {e}")
