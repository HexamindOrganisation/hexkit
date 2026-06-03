"""
Test fixtures shared across the suite.

The key trick: a `FakeRuntime` is registered under the framework name
`"fake"` so the registry's discovery path (the same one used in production)
can load fake agents without touching LangChain.
"""

from __future__ import annotations

import asyncio
import textwrap
from pathlib import Path
from typing import AsyncIterator

import pytest

from platform_runtime.adapters import register_adapter
from platform_runtime.events import (
    ApprovalDecision,
    ApprovalKind,
    ApprovalSource,
    StreamEvent,
)
from platform_runtime.run_emitter import RunEmitter, extract_query
from platform_runtime.manifest import SUPPORTED_FRAMEWORKS
from platform_runtime.protocol import (
    AgentCapabilities,
    AgentMetadata,
    InvokeRequest,
    ToolDescriptor,
    UnifiedAgentRuntime,
)


# Whitelist "fake" as a supported framework for manifest validation.
# `frozenset` is immutable, so we replace it on the manifest module.
import platform_runtime.manifest as _manifest_mod

_manifest_mod.SUPPORTED_FRAMEWORKS = frozenset(SUPPORTED_FRAMEWORKS | {"fake"})


@register_adapter("fake")
class FakeRuntime(UnifiedAgentRuntime):
    """A scripted runtime that yields a deterministic event sequence.

    The factory's return value is a list of ``(kind, payload)`` tuples
    describing what to emit, in order. Recognized kinds:

      - ``("delta", {"block_key", "text"})``     — stream a text chunk
      - ``("end_block", {"block_key"})``          — finalize a text block
      - ``("tool_start", {"tool_id", "tool_name", "arguments"?})``
      - ``("tool_end", {"tool_id", "tool_name", "output"?})``
      - ``("state", {"key", "value"})``
      - ``("approval", {"approval_id", "source"?, "kind"?, "reason"?,
        "tool_name"?, "arguments"?})`` — emit an approval request, then
        SUSPEND until ``resume(run_id, approval_id, ...)`` is called
      - ``("sleep", {"seconds"})``                — delay (cancel races)
    """

    def __init__(self, *, manifest, root: Path, factory) -> None:
        self._manifest = manifest
        self._root = root
        self._factory = factory
        self._script = factory()
        self._cancel_signals: dict[str, asyncio.Event] = {}
        # (run_id, approval_id) -> Future resolved by `resume()` / `cancel()`.
        self._approvals: dict[tuple[str, str], asyncio.Future] = {}

    async def stream(self, request: InvokeRequest) -> AsyncIterator[StreamEvent]:
        emitter = RunEmitter(request.run_id, agent_id=self._manifest.agent_id)
        cancel_signal = asyncio.Event()
        self._cancel_signals[request.run_id] = cancel_signal
        loop = asyncio.get_running_loop()

        try:
            for ev in emitter.run_start(
                query=extract_query(request.input),
                input={"value": request.input},
            ):
                yield ev
            for kind, payload in self._script:
                if cancel_signal.is_set():
                    for ev in emitter.error(
                        "Run cancelled", details={"cancelled": True}
                    ):
                        yield ev
                    return

                if kind == "sleep":
                    await asyncio.sleep(payload.get("seconds", 0.0))
                elif kind == "delta":
                    for ev in emitter.text_delta(
                        payload["block_key"], payload["text"]
                    ):
                        yield ev
                elif kind == "end_block":
                    for ev in emitter.end_block(payload["block_key"]):
                        yield ev
                elif kind == "tool_start":
                    for ev in emitter.tool_start(
                        tool_id=payload["tool_id"],
                        tool_name=payload["tool_name"],
                        arguments=payload.get("arguments", {}),
                    ):
                        yield ev
                elif kind == "tool_end":
                    for ev in emitter.tool_end(
                        tool_id=payload["tool_id"],
                        tool_name=payload["tool_name"],
                        output=payload.get("output"),
                    ):
                        yield ev
                elif kind == "state":
                    for ev in emitter.state_update(
                        payload["key"], payload["value"]
                    ):
                        yield ev
                elif kind == "approval":
                    approval_id = payload["approval_id"]
                    for ev in emitter.approval_requested(
                        approval_id=approval_id,
                        source=ApprovalSource(payload.get("source", "policy")),
                        kind=ApprovalKind(payload.get("kind", "authorize")),
                        reason=payload.get("reason", ""),
                        tool_name=payload.get("tool_name"),
                        arguments=payload.get("arguments", {}),
                    ):
                        yield ev
                    # Suspend: await the out-of-band decision (or a cancel).
                    fut: asyncio.Future = loop.create_future()
                    self._approvals[(request.run_id, approval_id)] = fut
                    try:
                        decision_info = await fut
                    finally:
                        self._approvals.pop((request.run_id, approval_id), None)
                    if decision_info is None:  # cancelled while waiting
                        for ev in emitter.error(
                            "Run cancelled", details={"cancelled": True}
                        ):
                            yield ev
                        return
                    decision, decided_by = decision_info
                    for ev in emitter.approval_resolved(
                        approval_id=approval_id,
                        decision=decision,
                        decided_by=decided_by,
                    ):
                        yield ev
            for ev in emitter.run_end(output={"ok": True}):
                yield ev
        finally:
            self._cancel_signals.pop(request.run_id, None)

    async def cancel(self, run_id: str) -> bool:
        signal = self._cancel_signals.get(run_id)
        if signal is None or signal.is_set():
            return False
        signal.set()
        # Wake any approval the run is currently suspended on.
        for (rid, aid), fut in list(self._approvals.items()):
            if rid == run_id and not fut.done():
                fut.set_result(None)
        return True

    async def resume(
        self, run_id: str, approval_id: str, decision: str, payload=None
    ) -> bool:
        fut = self._approvals.get((run_id, approval_id))
        if fut is None or fut.done():
            return False
        decided_by = (payload or {}).get("decided_by")
        fut.set_result((ApprovalDecision(decision), decided_by))
        return True

    async def tools(self) -> list[ToolDescriptor]:
        return [
            ToolDescriptor(
                name="echo",
                description="Echoes its input.",
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                },
            )
        ]

    async def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id=self._manifest.agent_id,
            name=self._manifest.name,
            framework=self._manifest.framework,
            version=self._manifest.version,
            description=self._manifest.description,
            capabilities=AgentCapabilities(tools=True),
        )


@pytest.fixture
def fake_agent_dir(tmp_path: Path) -> Path:
    """Create a temp agent folder with manifest + entrypoint."""
    agent_dir = tmp_path / "my-fake"
    agent_dir.mkdir()
    (agent_dir / "agent.yaml").write_text(
        textwrap.dedent(
            """
            agent_id: my-fake
            name: My Fake Agent
            framework: fake
            entrypoint: agent.py
            agent_callable: build_agent
            version: 0.1.0
            description: scripted test agent
            """
        ).lstrip()
    )
    (agent_dir / "agent.py").write_text(
        textwrap.dedent(
            """
            def build_agent():
                # Each tuple drives one emitter call in the FakeRuntime stream.
                return [
                    ("delta", {"block_key": "m1", "text": "Hello"}),
                    ("delta", {"block_key": "m1", "text": " world"}),
                    ("end_block", {"block_key": "m1"}),
                    ("tool_start", {
                        "tool_id": "t1",
                        "tool_name": "echo",
                        "arguments": {"text": "hi"},
                    }),
                    ("tool_end", {
                        "tool_id": "t1",
                        "tool_name": "echo",
                        "output": "hi",
                    }),
                ]
            """
        ).lstrip()
    )
    return agent_dir
