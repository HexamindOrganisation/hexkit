"""LangChain / LangGraph / DeepAgents translator.

Consumes the JSON projection of LangChain's ``astream_events(version="v2")``
stream. Ported from ``legacy/backend-runtime/.../adapters/langchain_adapter.py`` — the
event→emitter mapping, driven off the wire instead of a live ``Runnable``.

    on_chat_model_stream / on_llm_stream   -> text block delta (keyed by run_id)
    on_chat_model_end   / on_llm_end       -> close block (or full text from output)
    on_tool_start                          -> tool_start (keyed by run_id)
    on_tool_end                            -> tool_end
    (on_chain_*, on_retriever_*, ... ignored)

Wire shape of one event (``data:`` payload's ``event`` field):
    {"event":"on_chat_model_stream","run_id":"abc","name":"chat",
     "data":{"chunk":{"content":"Hello "}}}
"""

from __future__ import annotations

import uuid
from typing import Any

from hexa_events import RunEmitter, StreamEvent

from .base import BaseTranslator, coerce_args, extract_text


class LangChainTranslator(BaseTranslator):
    def __init__(self) -> None:
        # LangChain tool-run id -> our minted tool_id.
        self._tool_ids: dict[str, str] = {}

    def handle(self, emitter: RunEmitter, event: dict[str, Any]) -> list[StreamEvent]:
        name = event.get("event")
        lc_run_id = event.get("run_id", "") or "main"
        data = event.get("data") or {}

        if name in ("on_chat_model_stream", "on_llm_stream"):
            return emitter.text_delta(lc_run_id, extract_text(data.get("chunk")))

        if name in ("on_chat_model_end", "on_llm_end"):
            if emitter.has_block(lc_run_id):
                return emitter.end_block(lc_run_id)
            return emitter.full_text_block(extract_text(data.get("output")))

        if name == "on_tool_start":
            tool_id = uuid.uuid4().hex
            self._tool_ids[event.get("run_id", "")] = tool_id
            return emitter.tool_start(
                tool_id=tool_id,
                tool_name=event.get("name", "tool"),
                arguments=coerce_args(data.get("input")),
            )

        if name == "on_tool_end":
            tool_id = self._tool_ids.pop(event.get("run_id", ""), uuid.uuid4().hex)
            return emitter.tool_end(
                tool_id=tool_id,
                tool_name=event.get("name", "tool"),
                output=data.get("output"),
            )

        return []
