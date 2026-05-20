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

from .events import RunCompleted, RuntimeEvent


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
    async def stream(self, request: InvokeRequest) -> AsyncIterator[RuntimeEvent]:
        """Run the agent and yield normalized events as they occur.

        Implementations MUST:
        - emit a `RunStarted` as the first event and a `RunCompleted` (or
          `ErrorEvent`) as the last event;
        - assign a monotonically increasing `seq` to every event within the
          run, starting at 0;
        - propagate `request.run_id` onto every event;
        - never raise out of the generator after the first event has been
          yielded — failures after that point become `ErrorEvent`s.
        """
        raise NotImplementedError
        # The `yield` below makes this an async-generator type for static
        # analyzers; subclasses override entirely.
        yield  # type: ignore[unreachable]

    async def invoke(self, request: InvokeRequest) -> RunCompleted:
        """Drain `stream` and return the terminal `RunCompleted` event.

        Default implementation suits any adapter whose `stream` already
        emits a `RunCompleted`. Adapters with a cheaper non-streaming path
        may override this for efficiency.
        """
        terminal: RunCompleted | None = None
        async for event in self.stream(request):
            if isinstance(event, RunCompleted):
                terminal = event
        if terminal is None:
            raise RuntimeError(
                "Adapter stream finished without emitting RunCompleted"
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

    async def aclose(self) -> None:
        """Release any resources held by the adapter. Default no-op."""
        return None
