"""
Human-in-the-loop approval flow over the subprocess IPC wire.

The in-process variant lives in ``test_approvals.py``. This one proves the
SAME suspend/resume contract survives ``PLATFORM_ISOLATION=subprocess``: the
run suspends inside a real worker process and an out-of-band
``runtime.resume(...)`` — what ``POST .../approvals/{id}`` forwards — is
carried by ``RemoteAdapter.resume`` over the JSON-lines wire to the worker's
adapter, which resolves the pause so the run continues. Before the wire
plumbing existed, ``RemoteAdapter`` inherited the default ``resume() -> False``
and the run would hang at the pause forever; the endpoint returned
``{"resolved": false}``.

The streaming test drives the ``RemoteAdapter`` directly (the same level
``test_cancel.py`` works at) rather than through the SSE endpoint: httpx's
``ASGITransport`` buffers a streaming response, so an in-loop ``aiter_lines``
consumer never observes the mid-run pause event needed to trigger the resume.
Driving the adapter exercises exactly the changed code (``RemoteAdapter`` →
wire ``resume`` method → worker dispatch) without that artifact.

A spawned worker is a fresh ``python -m platform_runtime.worker`` process that
only registers the real framework adapters — it has never heard of the test
``fake`` framework. We bridge that by dropping a ``sitecustomize.py`` that
imports the test ``conftest`` (whose import side effects register the
``FakeRuntime`` adapter and whitelist ``fake``) and putting it plus the tests
dir on the child's ``PYTHONPATH`` so the interpreter runs it at startup.
"""

from __future__ import annotations

import asyncio
import os
import textwrap
from pathlib import Path

import httpx
import pytest

from platform_runtime.adapters.remote_adapter import RemoteAdapter
from platform_runtime.protocol import InvokeRequest
from platform_runtime.registry import AgentRegistry, IsolationMode
from platform_runtime.server import create_app


TESTS_DIR = Path(__file__).resolve().parent


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


def _enable_fake_framework_in_worker(monkeypatch: pytest.MonkeyPatch, boot_dir: Path) -> None:
    """Make a spawned worker able to host the ``fake`` framework.

    The worker inherits the parent's environment (the supervisor spawns it
    with ``env=None``), so prepending to ``PYTHONPATH`` here reaches the
    child. ``sitecustomize`` is auto-imported by the ``site`` module before
    ``-m platform_runtime.worker`` runs, so the adapter is registered and
    ``SUPPORTED_FRAMEWORKS`` patched before the worker validates the manifest.
    """
    boot_dir.mkdir(exist_ok=True)
    (boot_dir / "sitecustomize.py").write_text("import conftest  # noqa: F401\n")
    parts = [str(boot_dir), str(TESTS_DIR)]
    existing = os.environ.get("PYTHONPATH", "")
    if existing:
        parts.append(existing)
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(parts))


@pytest.mark.subprocess
@pytest.mark.asyncio
async def test_approval_resume_over_subprocess_wire(
    approval_agent_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_fake_framework_in_worker(monkeypatch, tmp_path / "boot")

    reg = AgentRegistry(isolation=IsolationMode.SUBPROCESS)
    reg.load(approval_agent_dir)

    # start_all() spawns the worker; aclose() tears it down.
    await reg.start_all()
    try:
        runtime = reg.get("approval-fake").runtime
        assert isinstance(runtime, RemoteAdapter)  # proves we're on the wire

        req = InvokeRequest(
            input={"messages": [{"role": "user", "content": "delete it"}]},
            run_id="run-sub",
        )
        events: list = []

        async def drain() -> None:
            async for ev in runtime.stream(req):
                events.append(ev)

        task = asyncio.create_task(drain())

        # Wait until the run has emitted the approval request and suspended
        # inside the worker.
        for _ in range(200):
            await asyncio.sleep(0.02)
            if any(
                type(e).__name__ == "ApprovalRequestedEvent" for e in events
            ):
                break
        names = [type(e).__name__ for e in events]
        assert "ApprovalRequestedEvent" in names, f"never paused: {names}"
        # Suspended: the gated tool must NOT have run yet.
        assert "ToolStartEvent" not in names

        req_ev = next(
            e for e in events if type(e).__name__ == "ApprovalRequestedEvent"
        )
        assert req_ev.tool_name == "delete_file"

        # Resolve out of band — forwarded by RemoteAdapter.resume over the
        # JSON-lines wire to the worker's adapter.
        ok = await runtime.resume(
            "run-sub", req_ev.approval_id, "approved", {"decided_by": "dev01"}
        )
        assert ok is True

        await asyncio.wait_for(task, timeout=5.0)

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

        # Resuming an already-resolved approval over the wire is a no-op.
        assert (
            await runtime.resume("run-sub", req_ev.approval_id, "approved")
            is False
        )
    finally:
        await reg.aclose()


@pytest.mark.subprocess
@pytest.mark.asyncio
async def test_resume_unknown_approval_over_wire_returns_false(
    approval_agent_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A resume for a run/approval the worker has never paused on returns
    ``{"resolved": false}`` — the wire forwards the adapter's real answer
    rather than the old default-False stub."""
    _enable_fake_framework_in_worker(monkeypatch, tmp_path / "boot")

    reg = AgentRegistry(isolation=IsolationMode.SUBPROCESS)
    reg.load(approval_agent_dir)
    app = create_app(reg)

    await reg.start_all()
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            r = await client.post(
                "/agents/approval-fake/runs/nope/approvals/nope",
                json={"decision": "approved"},
            )
            assert r.status_code == 200
            assert r.json() == {"resolved": False}
    finally:
        await reg.aclose()
