"""The `native` translator — for developers not on a supported framework.

The escape hatch: the backend emits already-normalized minimal events and the
proxy does almost nothing. This is the simple format for custom agent loops or
unsupported frameworks.

    {"type": "text",        "text": "..."}
    {"type": "reasoning",   "text": "..."}
    {"type": "tool",        "id": "t1", "name": "search", "args": {...}, "widget": "..."}
    {"type": "tool_result", "id": "t1", "output": {...} | "error": "..."}
    {"type": "error",       "message": "..."}
    {"type": "done"}                            (handled by the chat route)
"""

from __future__ import annotations

import uuid
from typing import Any

from hexa_events import BlockType, RunEmitter, StreamEvent

from .base import DEFAULT_TOOL_WIDGET, BaseTranslator


class NativeTranslator(BaseTranslator):
    def __init__(self) -> None:
        # tool_id -> (name, widget), captured at `tool` for use at `tool_result`.
        self._tools: dict[str, tuple[str, str | None]] = {}
        self._last_tool_id: str | None = None

    def handle(self, emitter: RunEmitter, event: dict[str, Any]) -> list[StreamEvent]:
        etype = event.get("type")

        if etype == "text":
            return emitter.text_delta("main", event.get("text", "") or "")

        if etype == "reasoning":
            return emitter.text_delta(
                "reasoning", event.get("text", "") or "", block_type=BlockType.REASONING
            )

        if etype == "tool":
            tool_id = event.get("id") or uuid.uuid4().hex
            name = event.get("name") or "tool"
            widget = event.get("widget") or DEFAULT_TOOL_WIDGET
            self._tools[tool_id] = (name, widget)
            self._last_tool_id = tool_id
            return emitter.tool_start(
                tool_id=tool_id,
                tool_name=name,
                arguments=event.get("args") or {},
                widget=widget,
            )

        if etype == "tool_result":
            tool_id = event.get("id") or self._last_tool_id or uuid.uuid4().hex
            name, widget = self._tools.pop(
                tool_id, (event.get("name") or "tool", DEFAULT_TOOL_WIDGET)
            )
            return emitter.tool_end(
                tool_id=tool_id,
                tool_name=name,
                output=event.get("output"),
                error=event.get("error"),
                widget=widget,
            )

        if etype == "error":
            return emitter.error(event.get("message", "") or "")

        # "done" and unknown types: nothing (run_end is synthesized by the route).
        return []
