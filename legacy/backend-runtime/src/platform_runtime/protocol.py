"""
The unified runtime protocol.

Every framework adapter (LangChain, OpenAI Agents SDK, Google ADK, ...) is a
subclass of `UnifiedAgentRuntime`. The HTTP server and the rest of the
platform interact with adapters ONLY through this interface.

Design notes
------------
- `stream` is the primary entry point. `invoke` is a convenience wrapper that
  drains the stream and returns the terminal output. Adapters typically only
  need to implement `stream`; `invoke` has a default implementation here.
- The interface is intentionally narrow. Things the platform does NOT
  standardize (planners, memory layouts, internal orchestration) stay inside
  the adapter and the wrapped agent.
- Method signatures are async so the same interface works whether the adapter
  runs in-process today or talks to a subprocess/container worker tomorrow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator
from uuid import uuid4

from pydantic import BaseModel, Field

from .events import RunEndEvent, StreamEvent


# ---------------------------------------------------------------------------
# Request / descriptor models
# ---------------------------------------------------------------------------

class InvokeRequest(BaseModel):
    """One invocation of an agent.

    - `input` is free-form per agent (chat message, structured payload, ...).
      The adapter is responsible for mapping it onto the wrapped agent's
      expected shape.
    - `run_id` is supplied by the caller when it wants to correlate events
      (e.g. resume after disconnect). If omitted, the adapter assigns one.
    - `context` carries platform-level metadata (tenant, user, conversation
      id, secrets handle, ...) that the adapter may forward to the agent
      but the agent is not required to understand.
    """

    input: Any
    run_id: str = Field(default_factory=lambda: uuid4().hex)
    context: dict[str, Any] = Field(default_factory=dict)


class Credentials(BaseModel):
    """Per-user credentials passed through `InvokeRequest.context.credentials`.

    The platform backend decrypts the requesting user's API keys and forwards
    them here. Adapters that opt in read this struct and pass each value into
    the underlying framework client at agent-construction time. Adapters that
    don't opt in (no `credentials` kwarg on the agent factory) keep using
    process env vars as before — backwards compatible.

    All fields are optional: a user may only have set the key for one
    provider. Unknown providers stay out of this struct on purpose (the runtime
    has a closed set of supported frameworks).
    """

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None


class ToolDescriptor(BaseModel):
    """Framework-agnostic description of a tool the agent can call.

    Adapters translate framework-native tool definitions into this shape so
    the UI / control plane can render tool catalogs uniformly.
    """

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] | None = None


class AgentCapabilities(BaseModel):
    streaming: bool = True
    tools: bool = False
    state: bool = False
    approvals: bool = False
    multi_turn: bool = True


class AgentMetadata(BaseModel):
    """Static identity + capability advertisement for the agent."""

    agent_id: str
    name: str
    framework: str
    version: str = "0.0.0"
    description: str = ""
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    # Names of UI-triggered actions the agent exposes via `actions.py`.
    # The front-end uses this to gate `dispatcher.has?.(name)` checks and
    # to know which actions can be forwarded to the runtime.
    actions: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class HealthStatus(BaseModel):
    ok: bool
    details: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# The protocol
# ---------------------------------------------------------------------------

class UnifiedAgentRuntime(ABC):
    """Abstract runtime interface implemented by every framework adapter."""

    @abstractmethod
    async def stream(self, request: InvokeRequest) -> AsyncIterator[StreamEvent]:
        """Run the agent and yield normalized events as they occur.

        Implementations MUST:
        - emit a `RunStartEvent` as the first event and a `RunEndEvent` (or
          `ErrorEvent`) as the last event;
        - assign a monotonically increasing `sequence` to every event within
          the run, starting at 1 (note: persisted steps share the counter, so
          emitted event sequences are strictly increasing but not contiguous);
        - propagate `request.run_id` onto every event;
        - never raise out of the generator after the first event has been
          yielded — failures after that point become `ErrorEvent`s.
        """
        raise NotImplementedError
        # The `yield` below makes this an async-generator type for static
        # analyzers; subclasses override entirely.
        yield  # type: ignore[unreachable]

    async def invoke(self, request: InvokeRequest) -> RunEndEvent:
        """Drain `stream` and return the terminal `RunEndEvent` event.

        Default implementation suits any adapter whose `stream` already
        emits a `RunEndEvent`. Adapters with a cheaper non-streaming path
        may override this for efficiency.
        """
        terminal: RunEndEvent | None = None
        async for event in self.stream(request):
            if isinstance(event, RunEndEvent):
                terminal = event
        if terminal is None:
            raise RuntimeError(
                "Adapter stream finished without emitting RunEndEvent"
            )
        return terminal

    @abstractmethod
    async def tools(self) -> list[ToolDescriptor]:
        """List the tools the wrapped agent exposes. May be empty."""

    @abstractmethod
    async def metadata(self) -> AgentMetadata:
        """Static identity and capability advertisement."""

    async def health(self) -> HealthStatus:
        """Liveness probe. Override for richer checks (model reachability, ...)."""
        return HealthStatus(ok=True)

    async def cancel(self, run_id: str) -> bool:
        """Request cancellation of an in-flight run.

        Returns True if a run with that id was found and signaled, False
        otherwise. Idempotent: calling twice on the same run is allowed
        and the second call returns False.

        Cancellation takes effect at the next event boundary inside the
        cancelled run's `stream()` loop — typically within the time it
        takes the framework to produce its next event (milliseconds during
        a token stream). Cancelling a run blocked on a slow non-streaming
        call may take longer; mid-call interruption is a future
        enhancement.

        Default implementation returns False (adapter does not support
        cancellation). Adapters opt in by overriding.
        """
        return False

    async def resume(
        self,
        run_id: str,
        approval_id: str,
        decision: str,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        """Resolve a pending human-in-the-loop approval and resume the run.

        Correlates with an `ApprovalRequestedEvent` previously emitted on
        `run_id` carrying `approval_id`. `decision` is an
        `ApprovalDecision` value ("approved" / "denied"); `payload` carries
        any structured input for `kind=input` requests. The run then emits a
        matching `ApprovalResolvedEvent` and continues.

        Returns True if a matching pending approval was found and resolved,
        False otherwise (unknown run/approval, already resolved, or this
        adapter does not support HITL). Default implementation returns False;
        adapters that emit `ApprovalRequestedEvent` opt in by overriding.
        """
        return False

    async def aclose(self) -> None:
        """Release any resources held by the adapter. Default no-op."""
        return None
