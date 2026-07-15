"""OpenAI Agents SDK translator.

Consumes the JSON projection of ``Runner.run_streamed(...).stream_events()``.
Ported from ``legacy/backend-runtime/.../adapters/openai_agents_adapter.py``.

    raw_response  (response.output_text.delta)   -> text block delta
    run_item      message_output_created         -> close block (or full text)
    run_item      tool_called                    -> tool_start
    run_item      tool_output                    -> tool_end
    (agent_updated, handoff_*, mcp_*, ... ignored)

Wire shapes (the ``event`` field):
    {"type":"raw_response","data":{"type":"response.output_text.delta","delta":"Hi "}}
    {"type":"run_item","name":"tool_called",
     "item":{"raw_item":{"call_id":"c1","name":"search","arguments":"{\\"q\\":\\"x\\"}"}}}
    {"type":"run_item","name":"tool_output",
     "item":{"raw_item":{"call_id":"c1","name":"search"},"output":{...}}}
    {"type":"run_item","name":"message_output_created",
     "item":{"raw_item":{"content":[{"text":"..."}]}}}
"""

from __future__ import annotations

import uuid
from typing import Any

from hexa_events import RunEmitter, StreamEvent

from .base import BaseTranslator, coerce_args, extract_text

# All streamed deltas in a run share one logical message block until a
# message_output_created finalizes it (the SDK doesn't key deltas by message).
_MSG_KEY = "msg"


class OpenAIAgentsTranslator(BaseTranslator):
    def __init__(self) -> None:
        # SDK call_id -> our minted tool_id.
        self._tool_ids: dict[str, str] = {}
        self._block_open = False

    def handle(self, emitter: RunEmitter, event: dict[str, Any]) -> list[StreamEvent]:
        etype = event.get("type")

        if etype == "error":
            return emitter.error(
                event.get("message", "") or "", details=event.get("details") or {}
            )

        if etype == "raw_response":
            data = event.get("data") or {}
            if data.get("type") == "response.output_text.delta":
                delta = data.get("delta", "") or ""
                if delta:
                    self._block_open = True
                return emitter.text_delta(_MSG_KEY, delta)
            return []

        if etype == "run_item":
            name = event.get("name")
            item = event.get("item") or {}

            if name == "message_output_created":
                if self._block_open and emitter.has_block(_MSG_KEY):
                    self._block_open = False
                    return emitter.end_block(_MSG_KEY)
                text = extract_text(item.get("raw_item") or {})
                return emitter.full_text_block(text) if text else []

            if name == "tool_called":
                raw = item.get("raw_item") or {}
                call_id = raw.get("call_id") or uuid.uuid4().hex
                tool_id = uuid.uuid4().hex
                self._tool_ids[call_id] = tool_id
                return emitter.tool_start(
                    tool_id=tool_id,
                    tool_name=raw.get("name", "tool"),
                    arguments=coerce_args(raw.get("arguments")),
                )

            if name == "tool_output":
                raw = item.get("raw_item") or {}
                call_id = raw.get("call_id", "")
                tool_id = self._tool_ids.pop(call_id, uuid.uuid4().hex)
                return emitter.tool_end(
                    tool_id=tool_id,
                    tool_name=raw.get("name", "tool"),
                    output=item.get("output"),
                )

        return []
