"""The minimal developer event format + SSE framing.

This is the entire surface a developer's backend has to emit. Each event is one
SSE frame — ``data: {compact-json}\\n\\n`` — on a ``text/event-stream`` response.
The HexaUI proxy normalizes these into the rich internal event schema,
synthesizing run ids, sequence numbers, block lifecycle, and the
``run_start`` / ``run_end`` envelope. Developers never construct any of that.

Event vocabulary (the `type` field):

    {"type": "text",        "text": "..."}                       assistant text chunk
    {"type": "reasoning",   "text": "..."}                       thinking chunk (optional)
    {"type": "tool",        "id": "t1", "name": "search",         a tool call begins
                            "args": {...}, "widget": "tool-calls"}  (args, widget optional)
    {"type": "tool_result", "id": "t1", "output": {...}}          a tool call ends
    {"type": "tool_result", "id": "t1", "error": "..."}             (output OR error)
    {"type": "error",       "message": "..."}                     the run failed
    {"type": "done"}                                              optional; EOF also ends

The builder functions below are conveniences; emitting the plain dicts directly
is equally valid.
"""

from __future__ import annotations

import json
from typing import Any


def text(s: str) -> dict:
    return {"type": "text", "text": s}


def reasoning(s: str) -> dict:
    return {"type": "reasoning", "text": s}


def tool(
    id: str,
    name: str,
    args: dict[str, Any] | None = None,
    widget: str | None = None,
) -> dict:
    ev: dict[str, Any] = {"type": "tool", "id": id, "name": name, "args": args or {}}
    if widget is not None:
        ev["widget"] = widget
    return ev


def tool_result(id: str, output: Any = None, error: str | None = None) -> dict:
    ev: dict[str, Any] = {"type": "tool_result", "id": id}
    if error is not None:
        ev["error"] = error
    else:
        ev["output"] = output
    return ev


def error(message: str) -> dict:
    return {"type": "error", "message": message}


def done() -> dict:
    return {"type": "done"}


def to_sse(event: dict) -> bytes:
    """Frame one minimal event as an SSE ``data:`` frame (raw bytes)."""
    body = json.dumps(event, separators=(",", ":"))
    return f"data: {body}\n\n".encode()


def last_user_text(input: dict[str, Any]) -> str:
    """Best-effort last user message from the ``{"messages": [...]}`` input."""
    messages = (input or {}).get("messages")
    if isinstance(messages, list):
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                return str(msg.get("content", ""))
    return ""


def caller(context: dict[str, Any]) -> dict[str, Any]:
    """Caller identity from ``context.user`` (CONTRACT.md §5).

    The proxy forwards the signed-in user as ``context.user = {id, name, role}``
    (any value may be ``None``). Policy-aware backends use it to scope per-call
    decisions to the calling user — see the HexGate-gated ``healthcare`` /
    ``devops`` agents, which read ``id`` and ``role`` here. Returns an empty dict
    when no user block was sent (standalone ``python -m`` runs, older proxies),
    so callers fall back to their own defaults.
    """
    return (context or {}).get("user") or {}
