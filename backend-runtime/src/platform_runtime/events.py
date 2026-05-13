"""
Normalized event schema for the unified agent runtime.

Every adapter (LangChain, OpenAI Agents SDK, Google ADK, ...) translates its
framework-native callbacks/streams into instances of these models. The HTTP
server forwards them to clients verbatim, and the UI / observability layers
consume them without knowing which framework produced them.

This module deliberately contains NO framework imports. It is the contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid4().hex


class EventType(str, Enum):
    """Closed set of event names the platform recognizes.

    Adapters MUST map their framework events to one of these. Anything that
    does not fit a known type goes into a generic `state.update` with a
    descriptive payload, or is dropped.
    """

    MESSAGE_DELTA = "message.delta"
    MESSAGE_COMPLETED = "message.completed"
    TOOL_START = "tool.start"
    TOOL_END = "tool.end"
    TRACE_SPAN = "trace.span"
    STATE_UPDATE = "state.update"
    APPROVAL_REQUESTED = "approval.requested"
    ERROR = "error"
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"


class BaseEvent(BaseModel):
    """Common envelope fields shared by every event.

    - `id` uniquely identifies the event (useful for replay / dedup).
    - `run_id` ties events together for one invocation of an agent.
    - `ts` is the server-side timestamp of when the event was produced.
    - `seq` is a monotonically increasing per-run sequence number that the
      emitter (the adapter) assigns. Clients use it to order events and to
      detect gaps.
    """

    id: str = Field(default_factory=_new_id)
    run_id: str
    ts: datetime = Field(default_factory=_utcnow)
    seq: int


class MessageDelta(BaseEvent):
    """A streaming chunk of an assistant message (token / partial text)."""

    type: Literal[EventType.MESSAGE_DELTA] = EventType.MESSAGE_DELTA
    message_id: str
    delta: str
    role: Literal["assistant"] = "assistant"


class MessageCompleted(BaseEvent):
    """A full message is finalized (assistant or user). Carries final text."""

    type: Literal[EventType.MESSAGE_COMPLETED] = EventType.MESSAGE_COMPLETED
    message_id: str
    role: Literal["assistant", "user", "system", "tool"]
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolStart(BaseEvent):
    type: Literal[EventType.TOOL_START] = EventType.TOOL_START
    tool_call_id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolEnd(BaseEvent):
    type: Literal[EventType.TOOL_END] = EventType.TOOL_END
    tool_call_id: str
    name: str
    output: Any = None
    error: str | None = None


class TraceSpan(BaseEvent):
    """A trace span emitted for observability. Mirrors OpenTelemetry shape."""

    type: Literal[EventType.TRACE_SPAN] = EventType.TRACE_SPAN
    span_id: str
    parent_span_id: str | None = None
    name: str
    start_ts: datetime
    end_ts: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class StateUpdate(BaseEvent):
    """Generic state change. Used when no more specific event fits.

    Example: agent's scratchpad updated, memory store changed, planner moved
    to a new step.
    """

    type: Literal[EventType.STATE_UPDATE] = EventType.STATE_UPDATE
    key: str
    value: Any


class ApprovalRequested(BaseEvent):
    """The agent is paused awaiting human approval (HITL).

    The platform backend correlates `approval_id` with a UI prompt and then
    resumes the run via a separate control endpoint.
    """

    type: Literal[EventType.APPROVAL_REQUESTED] = EventType.APPROVAL_REQUESTED
    approval_id: str
    reason: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ErrorEvent(BaseEvent):
    type: Literal[EventType.ERROR] = EventType.ERROR
    message: str
    recoverable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class RunStarted(BaseEvent):
    type: Literal[EventType.RUN_STARTED] = EventType.RUN_STARTED
    agent_id: str
    input: dict[str, Any] = Field(default_factory=dict)


class RunCompleted(BaseEvent):
    type: Literal[EventType.RUN_COMPLETED] = EventType.RUN_COMPLETED
    agent_id: str
    output: Any = None


RuntimeEvent = Union[
    MessageDelta,
    MessageCompleted,
    ToolStart,
    ToolEnd,
    TraceSpan,
    StateUpdate,
    ApprovalRequested,
    ErrorEvent,
    RunStarted,
    RunCompleted,
]
"""Discriminated union of every event an adapter is allowed to emit."""
