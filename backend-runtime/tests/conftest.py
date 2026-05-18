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
    ErrorEvent,
    MessageCompleted,
    MessageDelta,
    RunCompleted,
    RunStarted,
    RuntimeEvent,
    ToolEnd,
    ToolStart,
)
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

    The factory's return value is a list of (kind, **kwargs) tuples
    describing the events to emit, in order. Optionally, a tuple of
    ("sleep", {"seconds": 0.1}) introduces a delay between events — used
    by cancel tests to race the cancel request against the stream.
    """

    def __init__(self, *, manifest, root: Path, factory) -> None:
        self._manifest = manifest
        self._root = root
        self._factory = factory
        self._script = factory()
        self._cancel_signals: dict[str, asyncio.Event] = {}

    async def stream(self, request: InvokeRequest) -> AsyncIterator[RuntimeEvent]:
        seq = 0
        cancel_signal = asyncio.Event()
        self._cancel_signals[request.run_id] = cancel_signal

        def nxt() -> int:
            nonlocal seq
            n = seq
            seq += 1
            return n

        try:
            yield RunStarted(
                run_id=request.run_id,
                seq=nxt(),
                agent_id=self._manifest.agent_id,
                input={"value": request.input},
            )
            for kind, payload in self._script:
                if cancel_signal.is_set():
                    yield ErrorEvent(
                        run_id=request.run_id,
                        seq=nxt(),
                        message="Run cancelled",
                        recoverable=False,
                        details={"cancelled": True},
                    )
                    return
                if kind == "sleep":
                    await asyncio.sleep(payload.get("seconds", 0.0))
                    continue
                cls = {
                    "delta": MessageDelta,
                    "message_completed": MessageCompleted,
                    "tool_start": ToolStart,
                    "tool_end": ToolEnd,
                }[kind]
                yield cls(run_id=request.run_id, seq=nxt(), **payload)
            yield RunCompleted(
                run_id=request.run_id,
                seq=nxt(),
                agent_id=self._manifest.agent_id,
                output={"ok": True},
            )
        finally:
            self._cancel_signals.pop(request.run_id, None)

    async def cancel(self, run_id: str) -> bool:
        signal = self._cancel_signals.get(run_id)
        if signal is None or signal.is_set():
            return False
        signal.set()
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
                # Each tuple becomes one event in the FakeRuntime stream.
                return [
                    ("delta", {"message_id": "m1", "delta": "Hello"}),
                    ("delta", {"message_id": "m1", "delta": " world"}),
                    ("tool_start", {
                        "tool_call_id": "t1",
                        "name": "echo",
                        "arguments": {"text": "hi"},
                    }),
                    ("tool_end", {
                        "tool_call_id": "t1",
                        "name": "echo",
                        "output": "hi",
                    }),
                    ("message_completed", {
                        "message_id": "m1",
                        "role": "assistant",
                        "content": "Hello world",
                    }),
                ]
            """
        ).lstrip()
    )
    return agent_dir
