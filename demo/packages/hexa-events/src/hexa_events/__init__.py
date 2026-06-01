"""HexaUI streaming event schema + emit-side helpers.

The wire contract between a developer's agent backend and the HexaUI proxy.
Install via ``pip install -e demo/packages/hexa-events`` (or ``file:`` path) in
both the agent-server and the proxy so the schema can't drift.
"""

from __future__ import annotations

from .events import (
    AgentRunResult,
    BaseStreamEvent,
    BlockDeltaEvent,
    BlockEndEvent,
    BlockStartEvent,
    BlockType,
    ErrorEvent,
    EventType,
    ReasoningStep,
    RunEndEvent,
    RunNode,
    RunStartEvent,
    Step,
    StepType,
    StreamEvent,
    TextStep,
    ToolCallState,
    ToolCallStep,
    ToolEndEvent,
    ToolStartEvent,
    ToolUpdateEvent,
)
from .run_emitter import RunEmitter, extract_query, summarize_output
from .sse import to_sse_frame

__all__ = [
    # enums
    "EventType",
    "StepType",
    "BlockType",
    "ToolCallState",
    # envelope + steps
    "RunNode",
    "Step",
    "TextStep",
    "ReasoningStep",
    "ToolCallStep",
    "AgentRunResult",
    # events
    "BaseStreamEvent",
    "RunStartEvent",
    "BlockStartEvent",
    "BlockDeltaEvent",
    "BlockEndEvent",
    "ToolStartEvent",
    "ToolUpdateEvent",
    "ToolEndEvent",
    "RunEndEvent",
    "ErrorEvent",
    "StreamEvent",
    # emit-side
    "RunEmitter",
    "extract_query",
    "summarize_output",
    # wire
    "to_sse_frame",
]
