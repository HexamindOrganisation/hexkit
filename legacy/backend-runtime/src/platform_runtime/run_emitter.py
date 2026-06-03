"""
Emit-side helper for building a normalized :mod:`events` stream.

This is the inverse of Fortify's ``_RunAccumulator`` (in
``fortify.streaming.normalize``): adapters call high-level methods
(``text_delta``, ``tool_start``, ``run_end``, ...) and the emitter assigns
sequence numbers, manages the block lifecycle (open → delta → end), and
accumulates persisted :class:`~platform_runtime.events.Step` objects into the
final :class:`~platform_runtime.events.AgentRunResult`.

Every emit method returns a ``list`` of events so call sites are uniform::

    for ev in emitter.text_delta(model_run_id, chunk):
        yield ev

The block model: streamed text opens a TEXT block on the first delta for a
given ``block_key``; subsequent deltas extend it; ``end_block`` (or the next
``tool_start`` / ``run_end``) closes it and records a ``TextStep``. A run
with no visible text simply never opens a block — exactly the right behaviour
for a turn that only calls tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from .events import (
    AgentRunResult,
    ApprovalDecision,
    ApprovalKind,
    ApprovalRequestedEvent,
    ApprovalResolvedEvent,
    ApprovalSource,
    BlockDeltaEvent,
    BlockEndEvent,
    BlockStartEvent,
    BlockType,
    ErrorEvent,
    ReasoningStep,
    RunEndEvent,
    RunStartEvent,
    StateUpdateEvent,
    StreamEvent,
    TextStep,
    ToolCallState,
    ToolCallStep,
    ToolEndEvent,
    ToolStartEvent,
    TraceSpanEvent,
)


def extract_query(input: Any) -> str:
    """Best-effort human-readable query for ``RunStartEvent.query``.

    The platform's ``input`` is adapter-specific. For the common chat shape
    (``{"messages": [{"role", "content"}, ...]}``) we return the last user
    message; otherwise we stringify.
    """
    if isinstance(input, dict):
        messages = input.get("messages")
        if isinstance(messages, list):
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    return str(msg.get("content", ""))
        if not messages and "value" in input:
            return str(input["value"])
    if isinstance(input, str):
        return input
    return "" if input is None else str(input)


def summarize_output(output: Any) -> str | None:
    """Build a short summary string for a tool output (UI / step display)."""
    if output is None:
        return None
    if isinstance(output, str):
        compact = " ".join(output.split())
        return compact[:200] + ("..." if len(compact) > 200 else "")
    if isinstance(output, dict):
        if "title" in output and "url" in output:
            return f"{output.get('title') or 'Untitled'} ({output.get('url')})"
        if isinstance(output.get("results"), list):
            return f"{len(output['results'])} results"
        return str({k: output[k] for k in list(output)[:3]})
    if isinstance(output, list):
        return f"{len(output)} items"
    return str(output)


@dataclass
class _OpenBlock:
    block_id: str
    block_type: BlockType
    role: str
    parts: list[str] = field(default_factory=list)


class RunEmitter:
    """Builds normalized :class:`StreamEvent`s for one agent run.

    One instance per ``stream()`` call. Not thread-safe — a single run is a
    single async task.
    """

    def __init__(self, run_id: str, *, agent_id: str | None = None) -> None:
        self.run_id = run_id
        self.root_run_id = run_id
        self.agent_id = agent_id
        self._seq = 0
        self._steps: list[Any] = []
        self._message_parts: list[str] = []
        self._open: dict[str, _OpenBlock] = {}
        # tool_id -> arguments captured at tool_start (for the persisted step).
        self._tool_args: dict[str, dict[str, Any]] = {}

    # -- envelope -----------------------------------------------------------

    def _next(self) -> int:
        self._seq += 1
        return self._seq

    def _node(self) -> dict[str, Any]:
        """Per-event envelope fields. Flat run: root==run_id, no parent."""
        return {
            "run_id": self.run_id,
            "root_run_id": self.root_run_id,
            "parent_run_id": None,
            "depth": 0,
            "sequence": self._next(),
        }

    # -- run lifecycle ------------------------------------------------------

    def run_start(
        self, *, query: str, input: dict[str, Any] | None = None
    ) -> list[StreamEvent]:
        return [
            RunStartEvent(
                **self._node(),
                query=query,
                agent_id=self.agent_id,
                input=input or {},
            )
        ]

    def run_end(self, *, output: Any = None) -> list[StreamEvent]:
        out = self.close_open_blocks()
        result = AgentRunResult(
            run_id=self.run_id,
            root_run_id=self.root_run_id,
            message="".join(self._message_parts),
            steps=list(self._steps),
        )
        out.append(RunEndEvent(**self._node(), result=result, output=output))
        return out

    # -- content blocks -----------------------------------------------------

    def text_delta(
        self,
        block_key: str,
        text: str,
        *,
        block_type: BlockType = BlockType.TEXT,
        role: str = "assistant",
    ) -> list[StreamEvent]:
        """Stream a chunk into the block identified by ``block_key``.

        Opens the block (emitting ``block_start``) on first sight.
        """
        if not text:
            return []
        out: list[StreamEvent] = []
        blk = self._open.get(block_key)
        if blk is None:
            blk = _OpenBlock(
                block_id=uuid4().hex, block_type=block_type, role=role
            )
            self._open[block_key] = blk
            out.append(
                BlockStartEvent(
                    **self._node(),
                    block_id=blk.block_id,
                    block_type=blk.block_type,
                    role=role,
                )
            )
        blk.parts.append(text)
        out.append(
            BlockDeltaEvent(
                **self._node(),
                block_id=blk.block_id,
                block_type=blk.block_type,
                text=text,
                role=blk.role,
            )
        )
        return out

    def end_block(self, block_key: str) -> list[StreamEvent]:
        """Close an open block, recording its persisted step."""
        blk = self._open.pop(block_key, None)
        if blk is None:
            return []
        text = "".join(blk.parts)
        if blk.block_type == BlockType.REASONING:
            self._steps.append(ReasoningStep(**self._node(), text=text))
        else:
            self._steps.append(TextStep(**self._node(), text=text))
            self._message_parts.append(text)
        return [
            BlockEndEvent(
                **self._node(),
                block_id=blk.block_id,
                block_type=blk.block_type,
                role=blk.role,
            )
        ]

    def full_text_block(
        self, text: str, *, role: str = "assistant"
    ) -> list[StreamEvent]:
        """Emit a complete block (start + delta + end) for non-streamed text."""
        if not text:
            return []
        key = uuid4().hex
        out = self.text_delta(key, text, role=role)
        out += self.end_block(key)
        return out

    def has_block(self, block_key: str) -> bool:
        """Whether a streaming block was opened for ``block_key``."""
        return block_key in self._open

    def close_open_blocks(self) -> list[StreamEvent]:
        out: list[StreamEvent] = []
        for key in list(self._open):
            out += self.end_block(key)
        return out

    # -- tools --------------------------------------------------------------

    def tool_start(
        self, *, tool_id: str, tool_name: str, arguments: dict[str, Any] | None
    ) -> list[StreamEvent]:
        # Any in-progress streamed text is finalized before tool activity, so
        # the transcript order is text → tool → text.
        out = self.close_open_blocks()
        args = arguments or {}
        self._tool_args[tool_id] = args
        out.append(
            ToolStartEvent(
                **self._node(),
                tool_id=tool_id,
                tool_name=tool_name,
                arguments=args,
            )
        )
        return out

    def tool_end(
        self,
        *,
        tool_id: str,
        tool_name: str,
        output: Any = None,
        error: str | None = None,
        state: ToolCallState | None = None,
        output_summary: str | None = None,
    ) -> list[StreamEvent]:
        if state is None:
            state = (
                ToolCallState.FAILED if error else ToolCallState.COMPLETED
            )
        if output_summary is None:
            output_summary = error if error else summarize_output(output)
        self._steps.append(
            ToolCallStep(
                **self._node(),
                tool_name=tool_name,
                arguments=self._tool_args.pop(tool_id, {}),
                state=state,
                output_summary=output_summary,
                raw_output=output,
            )
        )
        return [
            ToolEndEvent(
                **self._node(),
                tool_id=tool_id,
                tool_name=tool_name,
                state=state,
                output_summary=output_summary,
                output=output,
            )
        ]

    # -- platform extensions ------------------------------------------------

    def state_update(self, key: str, value: Any) -> list[StreamEvent]:
        return [StateUpdateEvent(**self._node(), key=key, value=value)]

    def trace_span(
        self,
        *,
        span_id: str,
        name: str,
        start_ts: datetime,
        end_ts: datetime | None = None,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> list[StreamEvent]:
        return [
            TraceSpanEvent(
                **self._node(),
                span_id=span_id,
                parent_span_id=parent_span_id,
                name=name,
                start_ts=start_ts,
                end_ts=end_ts,
                attributes=attributes or {},
            )
        ]

    # -- errors -------------------------------------------------------------

    def error(
        self,
        message: str,
        *,
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> list[StreamEvent]:
        return [
            ErrorEvent(
                **self._node(),
                message=message,
                recoverable=recoverable,
                details=details or {},
            )
        ]

    # -- human-in-the-loop --------------------------------------------------

    def approval_requested(
        self,
        *,
        approval_id: str,
        source: ApprovalSource,
        kind: ApprovalKind = ApprovalKind.AUTHORIZE,
        reason: str = "",
        tool_name: str | None = None,
        arguments: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> list[StreamEvent]:
        return [
            ApprovalRequestedEvent(
                **self._node(),
                approval_id=approval_id,
                source=source,
                kind=kind,
                reason=reason,
                tool_name=tool_name,
                arguments=arguments or {},
                payload=payload or {},
            )
        ]

    def approval_resolved(
        self,
        *,
        approval_id: str,
        decision: ApprovalDecision,
        decided_by: str | None = None,
        note: str | None = None,
    ) -> list[StreamEvent]:
        return [
            ApprovalResolvedEvent(
                **self._node(),
                approval_id=approval_id,
                decision=decision,
                decided_by=decided_by,
                note=note,
            )
        ]
