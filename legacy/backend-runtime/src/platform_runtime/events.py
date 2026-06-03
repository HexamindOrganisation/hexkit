"""
Normalized event schema for the unified agent runtime.

THIS FILE IS THE SHARED CONTRACT with the Fortify runtime (``coolagents``).
Its core is a verbatim adoption of ``fortify.streaming.events`` so that a
Fortify-wrapped agent's event stream plugs into this platform without
translation. Three things are layered on top, clearly delimited below:

  1. CORE  — identical to ``fortify.streaming.events``. Envelope (RunNode +
     BaseStreamEvent), the block model, tool events, run lifecycle, error,
     and the persisted Step / AgentRunResult models.
  2. PLATFORM EXTENSIONS (additive) — ``trace_span`` and ``state_update``.
     These are observability events Fortify does not emit; its streams simply
     never produce them, and consumers degrade gracefully. Keeping them here
     means this platform's adapters don't lose capability during the merge.
  3. HUMAN-IN-THE-LOOP (proposed) — ``approval_requested`` /
     ``approval_resolved``. These are NEW on both sides. They turn what
     Fortify currently swallows into a failed tool call (a policy
     ``ApprovalRequiredError`` resolved by an inline handler) into a
     first-class, auditable pause/resume signal. The intent is that the
     Fortify team copies these two events (and the enums) into
     ``fortify.streaming.events`` unchanged.

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
# 1. CORE  — keep identical to fortify.streaming.events
# ===========================================================================


class EventType(StrEnum):
    """Closed set of event names the platform recognizes."""

    # --- Core (Fortify parity) ---------------------------------------------
    RUN_START = "run_start"
    BLOCK_START = "block_start"
    BLOCK_DELTA = "block_delta"
    BLOCK_END = "block_end"
    TOOL_START = "tool_start"
    TOOL_UPDATE = "tool_update"
    TOOL_END = "tool_end"
    RUN_END = "run_end"
    ERROR = "error"

    # --- Platform extensions (additive; Fortify never emits these) ---------
    TRACE_SPAN = "trace_span"
    STATE_UPDATE = "state_update"

    # --- Human-in-the-loop (proposed for joint adoption) -------------------
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"


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


class RunNode(BaseModel):
    """Shared ancestry metadata for events and steps.

    The hierarchy fields (``root_run_id`` / ``parent_run_id`` / ``depth``)
    let nested or multi-agent runs reconstruct their tree. In-process
    single-agent adapters set ``root_run_id == run_id``, ``parent_run_id
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


class BaseStreamEvent(RunNode):
    """Base model for normalized stream events."""

    event_id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_utcnow)


class RunStartEvent(BaseStreamEvent):
    """Signal that a run has started."""

    event_type: Literal[EventType.RUN_START] = EventType.RUN_START
    query: str
    # Additive (platform): agent identity + structured input. Fortify's
    # run_start carries only `query`; these default cleanly so the event
    # remains valid against the Fortify shape.
    agent_id: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)


class BlockStartEvent(BaseStreamEvent):
    """Signal that a content block has started."""

    event_type: Literal[EventType.BLOCK_START] = EventType.BLOCK_START
    block_id: str
    block_type: BlockType
    # Additive (platform): role lets a chat UI label the block without a
    # separate `message.completed`. Defaults to assistant — the only role
    # any current adapter produces.
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


class ToolUpdateEvent(BaseStreamEvent):
    """Signal that a running tool produced an intermediate update."""

    event_type: Literal[EventType.TOOL_UPDATE] = EventType.TOOL_UPDATE
    tool_id: str
    tool_name: str
    text: str


class ToolEndEvent(BaseStreamEvent):
    """Signal that a tool execution has completed."""

    event_type: Literal[EventType.TOOL_END] = EventType.TOOL_END
    tool_id: str
    tool_name: str
    state: ToolCallState = ToolCallState.COMPLETED
    output_summary: str | None = None
    # Additive (platform): the raw, JSON-able tool output. Fortify keeps the
    # full payload only on the persisted ToolCallStep (`raw_output`) and puts
    # a summary on the wire. This platform's UI renders full outputs, so we
    # also carry it here. Optional — emitters may leave it None for large
    # payloads and let consumers fall back to the step.
    output: Any = None


class RunEndEvent(BaseStreamEvent):
    """Signal that a run has completed with a final result."""

    event_type: Literal[EventType.RUN_END] = EventType.RUN_END
    result: AgentRunResult
    # Additive (platform): the terminal output value (LangGraph terminal
    # state, OpenAI final_output, ...). `result.message` carries the text;
    # this preserves the structured terminal payload the old `run.completed`
    # event exposed.
    output: Any = None


class ErrorEvent(BaseStreamEvent):
    """Signal that a run or child node has failed."""

    event_type: Literal[EventType.ERROR] = EventType.ERROR
    message: str
    # Additive (platform): richer error context. Fortify's error carries only
    # `message`; these default cleanly.
    recoverable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


# ===========================================================================
# 2. PLATFORM EXTENSIONS  — additive observability (Fortify never emits these)
# ===========================================================================


class TraceSpanEvent(BaseStreamEvent):
    """A trace span emitted for observability. Mirrors OpenTelemetry shape.

    Fortify encodes ancestry on every event via RunNode rather than emitting
    spans; a monitor can synthesize the span tree from `root/parent/depth`.
    This event is for adapters (LangChain chain spans) that have richer
    timing to surface directly.
    """

    event_type: Literal[EventType.TRACE_SPAN] = EventType.TRACE_SPAN
    span_id: str
    parent_span_id: str | None = None
    name: str
    start_ts: datetime
    end_ts: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class StateUpdateEvent(BaseStreamEvent):
    """Generic state change. Used when no more specific event fits.

    Example: a multi-agent handoff (`key="active_agent"`), a planner step,
    a scratchpad update.
    """

    event_type: Literal[EventType.STATE_UPDATE] = EventType.STATE_UPDATE
    key: str
    value: Any


# ===========================================================================
# 3. HUMAN-IN-THE-LOOP  — proposed for joint adoption (copy into Fortify)
# ===========================================================================


class ApprovalSource(StrEnum):
    """What triggered the pause.

    Distinct from *who resolves it* (in the bundle, almost always a human in
    the UI in both cases). The axis that matters is the trigger:
    """

    POLICY = "policy"  # a governance/policy gate interposed on an action
    AGENT = "agent"  # agent-initiated elicitation / clarification


class ApprovalKind(StrEnum):
    """The shape of answer the requester expects back."""

    AUTHORIZE = "authorize"  # approve / deny a proposed action
    INPUT = "input"  # supply free-form or structured input


class ApprovalDecision(StrEnum):
    """Outcome carried by the resolution event / the resume control call."""

    APPROVED = "approved"
    DENIED = "denied"


class ApprovalRequestedEvent(BaseStreamEvent):
    """The run is suspended awaiting an out-of-band decision (HITL).

    The runtime emits this, then pauses. The decision arrives on a separate
    control channel (``POST /agents/{id}/runs/{run_id}/approvals/{approval_id}``)
    keyed by ``approval_id``, after which the run resumes and emits a matching
    :class:`ApprovalResolvedEvent`.
    """

    event_type: Literal[EventType.APPROVAL_REQUESTED] = (
        EventType.APPROVAL_REQUESTED
    )
    approval_id: str
    source: ApprovalSource
    kind: ApprovalKind = ApprovalKind.AUTHORIZE
    reason: str = ""
    # Set when a tool call is being gated (the common policy case).
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    # Escape hatch: input schema for `kind=input`, option lists, policy id, ...
    payload: dict[str, Any] = Field(default_factory=dict)


class ApprovalResolvedEvent(BaseStreamEvent):
    """A previously requested approval was decided and the run resumed.

    This is the audit artifact: who decided, what they decided, and when.
    """

    event_type: Literal[EventType.APPROVAL_RESOLVED] = (
        EventType.APPROVAL_RESOLVED
    )
    approval_id: str
    decision: ApprovalDecision
    decided_by: str | None = None
    note: str | None = None


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
    | ErrorEvent
    # platform extensions
    | TraceSpanEvent
    | StateUpdateEvent
    # human-in-the-loop
    | ApprovalRequestedEvent
    | ApprovalResolvedEvent,
    Field(discriminator="event_type"),
]
"""Discriminated union of every event an adapter is allowed to emit."""

# Backwards-compatible alias. Internal call sites historically typed the
# union as ``RuntimeEvent``; keep the name resolvable during/after migration.
RuntimeEvent = StreamEvent
