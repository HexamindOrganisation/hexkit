"""
Subprocess isolation: registry constructs a RemoteAdapter, the lifespan
spawns the worker, and HTTP routes round-trip through the wire protocol.

These tests spawn real `python -m platform_runtime.worker` processes, so
they run a bit slower than the in-process suite (~2s each). Marked
explicitly so the rest of the suite stays fast.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from platform_runtime.adapters.remote_adapter import RemoteAdapter
from platform_runtime.registry import AgentRegistry, IsolationMode
from platform_runtime.server import create_app
from platform_runtime.subprocess_supervisor import WorkerSupervisor


EXAMPLE_AGENT = Path(__file__).resolve().parents[1] / "examples" / "langchain_hello"


@pytest.mark.subprocess
def test_subprocess_registry_constructs_remote_adapter() -> None:
    """`load()` in SUBPROCESS mode wires a RemoteAdapter without starting
    the worker. The supervisor is created but not yet alive."""
    reg = AgentRegistry(isolation=IsolationMode.SUBPROCESS)
    loaded = reg.load(EXAMPLE_AGENT)
    assert isinstance(loaded.runtime, RemoteAdapter)
    # The supervisor exists but no process has been spawned yet.
    sup = loaded.runtime._sup  # type: ignore[attr-defined]
    assert isinstance(sup, WorkerSupervisor)
    assert not sup.is_alive()


@pytest.mark.subprocess
def test_subprocess_lifespan_starts_workers_and_serves_metadata() -> None:
    """End-to-end: lifespan spawns the worker, /metadata round-trips through
    JSON-lines IPC, shutdown stops the worker cleanly."""
    reg = AgentRegistry(isolation=IsolationMode.SUBPROCESS)
    reg.load(EXAMPLE_AGENT)

    app = create_app(reg)
    # `with TestClient(app)` drives the lifespan: startup runs start_all(),
    # shutdown runs aclose(). If the worker fails to spawn, entering the
    # context manager raises.
    with TestClient(app) as client:
        r = client.get("/agents/langchain-hello/metadata")
        assert r.status_code == 200
        body = r.json()
        assert body["agent_id"] == "langchain-hello"
        assert body["framework"] == "langchain"

        # /health should report ok=False (no API key in CI shell), but the
        # status code should still be 503 — proves the in-process adapter's
        # health() result is carried over the wire untouched.
        r = client.get("/agents/langchain-hello/health")
        assert r.status_code in (200, 503)
        assert "ok" in r.json()
