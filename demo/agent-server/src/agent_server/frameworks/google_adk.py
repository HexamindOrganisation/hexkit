"""Project Google ADK runtime events into HexaUI native events.

Reusable for any real ADK runtime: ``to_native_event`` maps one ADK ``Event``
to the native JSON event the proxy's ``GoogleADKTranslator`` reads. The
agent-server side counterpart of ``openai_agents`` / ``langchain_events``.
"""

from __future__ import annotations

from typing import Any


def to_native_event(event: Any) -> dict | None:
    """Project one ADK ``Event`` into the native JSON the proxy's
    ``GoogleADKTranslator`` reads (``None`` to drop it).

    Mirrors the wire shape the translator expects: ``author`` + ``content.parts``
    of ``text`` / ``function_call`` / ``function_response``, with ``partial`` and
    ``turn_complete`` carried through so block framing stays correct.
    """
    content = getattr(event, "content", None)
    raw_parts = getattr(content, "parts", None) or []

    parts: list[dict] = []
    for part in raw_parts:
        func_call = getattr(part, "function_call", None)
        func_resp = getattr(part, "function_response", None)
        text = getattr(part, "text", None)
        if func_call is not None:
            parts.append(
                {
                    "function_call": {
                        "id": getattr(func_call, "id", None) or "",
                        "name": getattr(func_call, "name", "tool") or "tool",
                        "args": dict(getattr(func_call, "args", None) or {}),
                    }
                }
            )
        elif func_resp is not None:
            parts.append(
                {
                    "function_response": {
                        "id": getattr(func_resp, "id", None) or "",
                        "name": getattr(func_resp, "name", "tool") or "tool",
                        "response": getattr(func_resp, "response", None),
                    }
                }
            )
        elif text:
            parts.append({"text": text})

    turn_complete = bool(getattr(event, "turn_complete", False))
    if not parts and not turn_complete:
        return None

    native: dict[str, Any] = {
        "author": getattr(event, "author", None) or "assistant",
        "content": {"parts": parts},
    }
    if getattr(event, "partial", False):
        native["partial"] = True
    if turn_complete:
        native["turn_complete"] = True
    return native
