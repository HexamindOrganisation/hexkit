"""
Human-in-the-loop approval flow.

Demonstrates the proposed pause/resume contract: a run emits an
``ApprovalRequestedEvent`` and suspends; an out-of-band ``resume(...)`` call
(what the HTTP endpoint forwards) supplies the decision; the run emits an
``ApprovalResolvedEvent`` and continues. This is the reference behaviour the
Fortify side mirrors when it replaces its inline ``approval_handler``.
"""

from __future__ import annotations

import asyncio
import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from platform_runtime.protocol import InvokeRequest
from platform_runtime.registry import AgentRegistry
from platform_runtime.server import create_app


@pytest.fixture
def approval_agent_dir(tmp_path: Path) -> Path:
    """A fake agent that pauses for a policy approval before a tool call."""
    agent_dir = tmp_path / "approval-fake"
    agent_dir.mkdir()
    (agent_dir / "agent.yaml").write_text(
        textwrap.dedent(
            """
            agent_id: approval-fake
            name: Approval Fake
            framework: fake
            entrypoint: agent.py
            agent_callable: build_agent
            """
        ).lstrip()
    )
    (agent_dir / "agent.py").write_text(
        textwrap.dedent(
            """
            def build_agent():
                return [
                    ("delta", {"block_key": "m", "text": "I will delete it."}),
                    ("end_block", {"block_key": "m"}),
                    ("approval", {
                        "approval_id": "ap1",
                        "source": "policy",
                        "kind": "authorize",
                        "reason": "deletion requires approval",
                        "tool_name": "delete_file",
                        "arguments": {"path": "/tmp/x"},
                    }),
                    ("tool_start", {
                        "tool_id": "t1",
                        "tool_name": "delete_file",
                        "arguments": {"path": "/tmp/x"},
                    }),
                    ("tool_end", {
                        "tool_id": "t1",
                        "tool_name": "delete_file",
                        "output": "deleted",
                    }),
                ]
            """
        ).lstrip()
    )
    return agent_dir


@pytest.mark.asyncio
async def test_approval_suspends_then_resumes(approval_agent_dir: Path) -> None:
    reg = AgentRegistry()
    runtime = reg.load(approval_agent_dir).runtime
    req = InvokeRequest(
        input={"messages": [{"role": "user", "content": "delete it"}]},
        run_id="run-a",
    )

    events: list = []

    async def drain() -> None:
        async for ev in runtime.stream(req):
            events.append(ev)

    task = asyncio.create_task(drain())

    # Wait until the run has emitted the approval request and suspended.
    for _ in range(100):
        await asyncio.sleep(0.01)
        if any(type(e).__name__ == "ApprovalRequestedEvent" for e in events):
            break
    names = [type(e).__name__ for e in events]
    assert "ApprovalRequestedEvent" in names
    # Suspended: the gated tool must NOT have run yet.
    assert "ToolStartEvent" not in names

    req_ev = next(
        e for e in events if type(e).__name__ == "ApprovalRequestedEvent"
    )
    assert req_ev.source.value == "policy"
    assert req_ev.tool_name == "delete_file"

    # Resolve the approval out of band (what POST /approvals/{id} forwards).
    ok = await runtime.resume(
        "run-a", req_ev.approval_id, "approved", {"decided_by": "dev01"}
    )
    assert ok is True

    await asyncio.wait_for(task, timeout=2.0)

    names = [type(e).__name__ for e in events]
    # Resolution lands after the request, and the gated tool then runs.
    assert names.index("ApprovalResolvedEvent") > names.index(
        "ApprovalRequestedEvent"
    )
    assert "ToolStartEvent" in names
    assert "RunEndEvent" in names

    resolved = next(
        e for e in events if type(e).__name__ == "ApprovalResolvedEvent"
    )
    assert resolved.decision.value == "approved"
    assert resolved.decided_by == "dev01"

    # Resuming an already-resolved approval is a no-op.
    assert await runtime.resume("run-a", req_ev.approval_id, "approved") is False


def test_resume_unknown_approval_returns_false(approval_agent_dir: Path) -> None:
    reg = AgentRegistry()
    reg.load(approval_agent_dir)
    with TestClient(create_app(reg)) as client:
        r = client.post(
            "/agents/approval-fake/runs/nope/approvals/nope",
            json={"decision": "approved"},
        )
        assert r.status_code == 200
        assert r.json() == {"resolved": False}
