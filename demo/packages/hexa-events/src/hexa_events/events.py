"""
Normalized event schema for the HexaUI streaming contract.

This module is the wire contract between a developer's agent backend and the
HexaUI proxy. It is a trimmed descendant of the old unified-runtime event
schema: the core lifecycle (run / block / tool / error) is preserved verbatim
so existing consumers and the proxy's SSE parser keep working unchanged, while
the framework-observability and human-in-the-loop layers are dropped.

Core events:
  - ``run_start``
  - ``block_start`` / ``block_delta`` / ``block_end``  (text + reasoning)
  - ``tool_start`` / ``tool_update`` / ``tool_end``
  - ``run_end``
  - ``error``

One additive change vs. the old core: the three tool events carry an optional
``widget: str | None`` so the UI can route a tool call to a named widget
(default target = the ``tool-calls`` widget). This is mandated by the existing
consumer ``custom-UI/src/runtime/agentBridge.ts`` whose tool-call variant is
``{ kind: "tool-call", widget: string, payload }``.

This module deliberately contains NO framework imports. It is the contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid4().hex


# ===========================================================================
# Enums
# ===========================================================================


class EventType(StrEnum):
    """Closed set of event names the contract recognizes."""

    RUN_START = "run_start"
    BLOCK_START = "block_start"
    BLOCK_DELTA = "block_delta"
    BLOCK_END = "block_end"
    TOOL_START = "tool_start"
    TOOL_UPDATE = "tool_update"
    TOOL_END = "tool_end"
    RUN_END = "run_end"
    ERROR = "error"


class StepType(StrEnum):
    """Persisted step types for a single agent run."""

    TEXT = "text_step"
    REASONING = "reasoning_step"
    TOOL_CALL = "tool_call_step"


class BlockType(StrEnum):
    """Block types emitted during streaming."""

    TEXT = "text"
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"


class ToolCallState(StrEnum):
    """Lifecycle states for tool call steps."""

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


# ===========================================================================
# Envelope + persisted steps
# ===========================================================================


class RunNode(BaseModel):
    """Shared ancestry metadata for events and steps.

    The hierarchy fields (``root_run_id`` / ``parent_run_id`` / ``depth``)
    let nested or multi-agent runs reconstruct their tree. In-process
    single-agent backends set ``root_run_id == run_id``, ``parent_run_id
    is None`` and ``depth == 0`` — a flat run is just the degenerate case.
    """

    run_id: str
    root_run_id: str
    parent_run_id: str | None = None
    depth: int = 0
    sequence: int


class BaseStep(RunNode):
    """Base model for persisted run steps."""

    id: str = Field(default_factory=_new_id)


class TextStep(BaseStep):
    """Persisted visible assistant text emitted during a run."""

    type: Literal[StepType.TEXT] = StepType.TEXT
    text: str = ""


class ReasoningStep(BaseStep):
    """Persisted reasoning text emitted during a run."""

    type: Literal[StepType.REASONING] = StepType.REASONING
    text: str = ""


class ToolCallStep(BaseStep):
    """Persisted tool call activity emitted during a run."""

    type: Literal[StepType.TOOL_CALL] = StepType.TOOL_CALL
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    state: ToolCallState = ToolCallState.STARTED
    output_summary: str | None = None
    raw_output: Any | None = None


Step = Annotated[
    TextStep | ReasoningStep | ToolCallStep, Field(discriminator="type")
]


class AgentRunResult(BaseModel):
    """Final result for one agent run."""

    run_id: str
    root_run_id: str
    message: str = ""
    steps: list[Step] = Field(default_factory=list)


# ===========================================================================
# Stream events
# ===========================================================================


class BaseStreamEvent(RunNode):
    """Base model for normalized stream events."""

    event_id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_utcnow)


class RunStartEvent(BaseStreamEvent):
    """Signal that a run has started."""

    event_type: Literal[EventType.RUN_START] = EventType.RUN_START
    query: str
    agent_id: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)


class BlockStartEvent(BaseStreamEvent):
    """Signal that a content block has started."""

    event_type: Literal[EventType.BLOCK_START] = EventType.BLOCK_START
    block_id: str
    block_type: BlockType
    role: Literal["assistant", "user", "system", "tool"] = "assistant"


class BlockDeltaEvent(BaseStreamEvent):
    """Signal that a content block produced streamed text."""

    event_type: Literal[EventType.BLOCK_DELTA] = EventType.BLOCK_DELTA
    block_id: str
    block_type: BlockType
    text: str
    role: Literal["assistant", "user", "system", "tool"] = "assistant"


class BlockEndEvent(BaseStreamEvent):
    """Signal that a content block has ended."""

    event_type: Literal[EventType.BLOCK_END] = EventType.BLOCK_END
    block_id: str
    block_type: BlockType
    role: Literal["assistant", "user", "system", "tool"] = "assistant"


class ToolStartEvent(BaseStreamEvent):
    """Signal that a tool execution has started."""

    event_type: Literal[EventType.TOOL_START] = EventType.TOOL_START
    tool_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    # Additive: route this tool call to a named UI widget. Defaults to the
    # `tool-calls` widget when None.
    widget: str | None = None


class ToolUpdateEvent(BaseStreamEvent):
    """Signal that a running tool produced an intermediate update."""

    event_type: Literal[EventType.TOOL_UPDATE] = EventType.TOOL_UPDATE
    tool_id: str
    tool_name: str
    text: str
    widget: str | None = None


class ToolEndEvent(BaseStreamEvent):
    """Signal that a tool execution has completed."""

    event_type: Literal[EventType.TOOL_END] = EventType.TOOL_END
    tool_id: str
    tool_name: str
    state: ToolCallState = ToolCallState.COMPLETED
    output_summary: str | None = None
    # The raw, JSON-able tool output. Optional — backends may leave it None
    # for large payloads and let consumers fall back to the persisted step.
    output: Any = None
    widget: str | None = None


class RunEndEvent(BaseStreamEvent):
    """Signal that a run has completed with a final result."""

    event_type: Literal[EventType.RUN_END] = EventType.RUN_END
    result: AgentRunResult
    # The terminal output value (final structured payload), if any.
    output: Any = None


class ErrorEvent(BaseStreamEvent):
    """Signal that a run or child node has failed."""

    event_type: Literal[EventType.ERROR] = EventType.ERROR
    message: str
    recoverable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


# ===========================================================================
# Discriminated union
# ===========================================================================

StreamEvent = Annotated[
    RunStartEvent
    | BlockStartEvent
    | BlockDeltaEvent
    | BlockEndEvent
    | ToolStartEvent
    | ToolUpdateEvent
    | ToolEndEvent
    | RunEndEvent
    | ErrorEvent,
    Field(discriminator="event_type"),
]
"""Discriminated union of every event a backend is allowed to emit."""
