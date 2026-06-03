"""
RemoteAdapter — implements `UnifiedAgentRuntime` over a `WorkerSupervisor`.

This is the parent-side mirror of the in-process adapters: it does not
import any framework code (LangChain, OpenAI Agents SDK, ...). Every call
goes over the IPC wire to the child worker, which hosts the real adapter.

There is exactly ONE RemoteAdapter per agent. It holds a supervisor that
owns the worker process. When the registry asks for the adapter, it gets
this proxy; nothing in the server process ever loads LangChain.

This adapter is NOT registered under any framework name in the adapter
registry — that registry is used by the in-process loading path. The
RemoteAdapter is constructed by the registry directly when isolation
mode is `SUBPROCESS` (see Piece 3).
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from pydantic import TypeAdapter

from ..events import RunEndEvent, StreamEvent
from ..protocol import (
    AgentMetadata,
    HealthStatus,
    InvokeRequest,
    ToolDescriptor,
    UnifiedAgentRuntime,
)
from ..subprocess_supervisor import WorkerSupervisor


# Single shared adapter for parsing the discriminated event union.
_EVENT_ADAPTER: TypeAdapter[StreamEvent] = TypeAdapter(StreamEvent)


class RemoteAdapter(UnifiedAgentRuntime):
    """Proxy `UnifiedAgentRuntime` that talks to a worker process."""

    def __init__(self, *, supervisor: WorkerSupervisor) -> None:
        self._sup = supervisor

    async def stream(
        self, request: InvokeRequest
    ) -> AsyncIterator[StreamEvent]:
        # Forward params over the wire. The worker reconstructs an
        # InvokeRequest on the other side; we hand it the JSON-mode dump
        # so anything Pydantic-native (UUIDs, datetimes) is wire-safe.
        params = request.model_dump(mode="json")
        async for raw in self._sup.stream_rpc("stream", params):
            # Each raw frame is a serialized StreamEvent. Parsing through
            # the discriminated union restores the typed subclass — same
            # contract the in-process adapters provide.
            yield _EVENT_ADAPTER.validate_python(raw)

    async def invoke(self, request: InvokeRequest) -> RunEndEvent:
        raw = await self._sup.rpc("invoke", request.model_dump(mode="json"))
        return RunEndEvent.model_validate(raw)

    async def tools(self) -> list[ToolDescriptor]:
        raw = await self._sup.rpc("tools")
        return [ToolDescriptor.model_validate(t) for t in raw]

    async def metadata(self) -> AgentMetadata:
        raw = await self._sup.rpc("metadata")
        return AgentMetadata.model_validate(raw)

    async def health(self) -> HealthStatus:
        raw = await self._sup.rpc("health")
        return HealthStatus.model_validate(raw)

    async def cancel(self, run_id: str) -> bool:
        raw = await self._sup.rpc("cancel", {"run_id": run_id})
        return bool(raw.get("cancelled", False))

    async def resume(
        self,
        run_id: str,
        approval_id: str,
        decision: str,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        raw = await self._sup.rpc(
            "resume",
            {
                "run_id": run_id,
                "approval_id": approval_id,
                "decision": decision,
                "payload": payload,
            },
        )
        return bool(raw.get("resolved", False))

    async def aclose(self) -> None:
        await self._sup.stop()
