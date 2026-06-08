"""Google ADK translator.

Consumes the JSON projection of ``Runner.run_async(...)``'s ``Event`` stream.
Ported from ``legacy/backend-runtime/.../adapters/google_adk_adapter.py``.

    text part, partial=True       -> text block delta (new block per author)
    text part, partial=False      -> close block (or full text)
    function_call part            -> tool_start  (also auto-closes open text block)
    function_response part        -> tool_end
    turn_complete                 -> close open block
    (author switch closes the open block; state_update is dropped)

Wire shape (the ``event`` field), one ADK Event:
    {"author":"assistant","partial":true,"turn_complete":false,
     "content":{"parts":[{"text":"Hello "}]}}
    {"author":"assistant","content":{"parts":[
        {"function_call":{"id":"c1","name":"search","args":{"q":"x"}}}]}}
    {"author":"assistant","content":{"parts":[
        {"function_response":{"id":"c1","name":"search","response":{...}}}]}}
"""

from __future__ import annotations

import uuid
from typing import Any

from hexa_events import RunEmitter, StreamEvent

from .base import BaseTranslator, coerce_args


class GoogleADKTranslator(BaseTranslator):
    def __init__(self) -> None:
        # ADK function_call.id -> our minted tool_id.
        self._tool_ids: dict[str, str] = {}
        self._msg_id: str | None = None
        self._msg_author: str | None = None
        self._last_author: str | None = None

    def handle(self, emitter: RunEmitter, event: dict[str, Any]) -> list[StreamEvent]:
        out: list[StreamEvent] = []

        # Author switch (multi-agent) closes the previous author's open block.
        author = event.get("author")
        if author and author != self._last_author:
            self._last_author = author
            if self._msg_id is not None and emitter.has_block(self._msg_id):
                out += emitter.end_block(self._msg_id)
            self._msg_id = None
            self._msg_author = None

        content = event.get("content") or {}
        parts = content.get("parts") or []
        partial = bool(event.get("partial", False))

        for part in parts:
            text = part.get("text")
            func_call = part.get("function_call")
            func_resp = part.get("function_response")

            if text:
                if partial:
                    if self._msg_id is None or self._msg_author != author:
                        self._msg_id = uuid.uuid4().hex
                        self._msg_author = author
                    out += emitter.text_delta(self._msg_id, text)
                else:
                    if self._msg_id is not None and emitter.has_block(self._msg_id):
                        out += emitter.end_block(self._msg_id)
                    else:
                        out += emitter.full_text_block(text)
                    self._msg_id = None
                    self._msg_author = None

            elif func_call is not None:
                call_id = func_call.get("id") or uuid.uuid4().hex
                tool_id = uuid.uuid4().hex
                self._tool_ids[call_id] = tool_id
                # tool_start auto-closes any open text block in the emitter.
                self._msg_id = None
                out += emitter.tool_start(
                    tool_id=tool_id,
                    tool_name=func_call.get("name", "tool"),
                    arguments=coerce_args(func_call.get("args")),
                )

            elif func_resp is not None:
                call_id = func_resp.get("id", "") or ""
                tool_id = self._tool_ids.pop(call_id, uuid.uuid4().hex)
                out += emitter.tool_end(
                    tool_id=tool_id,
                    tool_name=func_resp.get("name", "tool"),
                    output=func_resp.get("response"),
                )

        if event.get("turn_complete") and self._msg_id is not None:
            if emitter.has_block(self._msg_id):
                out += emitter.end_block(self._msg_id)
            self._msg_id = None
            self._msg_author = None

        return out
