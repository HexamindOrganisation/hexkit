"""Fortify translator.

Fortify (a sibling team's agent-runtime security SDK) wraps a framework runtime
and emits an *already-normalized* event stream via ``fortify.stream_agent(...)``.
That stream is a near-twin of this proxy's internal ``hexa_events`` schema —
both descend from the same unified-runtime event vocabulary (same ``event_type``
names, same ``block_type`` / ``ToolCallState``, same ``run_id`` / ``sequence``
envelope). The developer backend forwards those events as-is, tagged
``framework: "fortify"``; this translator maps them onto the shared
:class:`~hexa_events.RunEmitter`.

Even though the schemas line up field-for-field, this is NOT a raw passthrough.
The chat route owns the run envelope: it synthesizes ``run_start`` / ``run_end``
and is the single authority for sequence numbers (see
``routes/chat.py``). So we DROP fortify's own ``run_start`` / ``run_end`` /
``block_start`` and re-drive the emitter from the content events — keeping one
sequence space and one persisted ``AgentRunResult``, exactly like every other
framework translator.

Wire shape of one event (the backend does ``ev.model_dump(mode="json")``):

    {"event_type":"block_delta","block_id":"b1","block_type":"text","text":"Hi "}
    {"event_type":"block_end","block_id":"b1","block_type":"text"}
    {"event_type":"tool_start","tool_id":"t1","tool_name":"search","arguments":{...}}
    {"event_type":"tool_end","tool_id":"t1","tool_name":"search",
     "state":"completed","output_summary":"3 results"}
    {"event_type":"error","message":"..."}
"""

from __future__ import annotations

from typing import Any

from hexa_events import BlockType, RunEmitter, StreamEvent, ToolCallState

from .base import BaseTranslator


def _block_type(value: Any) -> BlockType:
    """Map fortify's block_type string onto our enum (default TEXT)."""
    try:
        return BlockType(value)
    except ValueError:
        return BlockType.TEXT


def _tool_state(value: Any) -> ToolCallState | None:
    """Map fortify's tool state string onto our enum (None when unknown)."""
    try:
        return ToolCallState(value)
    except ValueError:
        return None


class FortifyTranslator(BaseTranslator):
    """Drive the emitter from fortify's normalized stream events.

    Stateless beyond the emitter: fortify already carries the ``block_id`` /
    ``tool_id`` correlation we need, so unlike the LangChain translator there
    are no per-run id maps to keep.
    """

    def handle(self, emitter: RunEmitter, event: dict[str, Any]) -> list[StreamEvent]:
        et = event.get("event_type")

        # Streamed text / reasoning. Keyed by fortify's block_id, so the emitter
        # opens one block per fortify block (lazily, on first delta) and closes
        # it on the matching block_end below.
        if et == "block_delta":
            return emitter.text_delta(
                event.get("block_id", "main"),
                event.get("text", "") or "",
                block_type=_block_type(event.get("block_type")),
            )

        if et == "block_end":
            return emitter.end_block(event.get("block_id", "main"))

        if et == "tool_start":
            return emitter.tool_start(
                tool_id=event.get("tool_id") or "",
                tool_name=event.get("tool_name", "tool"),
                arguments=event.get("arguments") or {},
            )

        if et == "tool_end":
            state = _tool_state(event.get("state"))
            summary = event.get("output_summary")
            failed = state == ToolCallState.FAILED
            # Fortify carries a short ``output_summary`` string, not the raw
            # payload. Surface it as the tool output (or the error message when
            # the call failed) so the tool-calls widget + persisted step have
            # something to show.
            return emitter.tool_end(
                tool_id=event.get("tool_id") or "",
                tool_name=event.get("tool_name", "tool"),
                output=None if failed else summary,
                error=summary if failed else None,
                state=state,
                output_summary=summary,
            )

        if et == "error":
            return emitter.error(event.get("message", "") or "")

        # run_start / run_end / block_start: the chat route owns the envelope.
        # tool_update: the emitter has no intermediate-update channel (parity
        # with the other framework translators, which also drop it).
        return []
