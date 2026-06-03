"""
Cancel API: POST /agents/{id}/runs/{run_id}/cancel terminates an in-flight
run, the SSE stream emits a cancelled `error` event, and second/duplicate
cancel calls are idempotent.
"""

from __future__ import annotations

import asyncio
import json
import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from platform_runtime.registry import AgentRegistry
from platform_runtime.server import create_app


@pytest.fixture
def slow_agent_dir(tmp_path: Path) -> Path:
    """A fake agent whose stream pauses between events so a cancel HTTP
    call can race ahead of it."""
    agent_dir = tmp_path / "slow-fake"
    agent_dir.mkdir()
    (agent_dir / "agent.yaml").write_text(
        textwrap.dedent(
            """
            agent_id: slow-fake
            name: Slow Fake
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
                # The "sleep" entries make the stream slow enough that an
                # out-of-band cancel HTTP call has time to land before the
                # script finishes naturally.
                return [
                    ("delta", {"block_key": "m", "text": "tick"}),
                    ("sleep", {"seconds": 0.3}),
                    ("delta", {"block_key": "m", "text": "tock"}),
                    ("sleep", {"seconds": 0.3}),
                    ("end_block", {"block_key": "m"}),
                ]
            """
        ).lstrip()
    )
    return agent_dir


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    frames: list[tuple[str, dict]] = []
    for block in body.replace("\r\n", "\n").strip().split("\n\n"):
        evt = None
        data = None
        for line in block.splitlines():
            if line.startswith("event:"):
                evt = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data = json.loads(line[len("data:"):].strip())
        if evt and data is not None:
            frames.append((evt, data))
    return frames


def test_cancel_returns_false_for_unknown_run(slow_agent_dir: Path) -> None:
    reg = AgentRegistry()
    reg.load(slow_agent_dir)
    with TestClient(create_app(reg)) as client:
        r = client.post("/agents/slow-fake/runs/nonexistent/cancel")
        assert r.status_code == 200
        assert r.json() == {"cancelled": False}


def test_cancel_unknown_agent_is_404(slow_agent_dir: Path) -> None:
    reg = AgentRegistry()
    reg.load(slow_agent_dir)
    with TestClient(create_app(reg)) as client:
        r = client.post("/agents/no-such/runs/abc/cancel")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_cancel_terminates_in_flight_run(slow_agent_dir: Path) -> None:
    """Drive the adapter directly (no HTTP). Start `stream()`, cancel via
    `cancel(run_id)`, verify the stream emits the cancelled error event
    and ends before the natural script completion."""
    reg = AgentRegistry()
    loaded = reg.load(slow_agent_dir)
    runtime = loaded.runtime

    from platform_runtime.protocol import InvokeRequest
    req = InvokeRequest(input={"q": "hi"}, run_id="run-x")

    events: list = []

    async def drain() -> None:
        async for ev in runtime.stream(req):
            events.append(ev)

    drain_task = asyncio.create_task(drain())
    # Give the stream time to emit RunStarted + at least one delta + reach
    # its first sleep.
    await asyncio.sleep(0.1)

    cancelled = await runtime.cancel("run-x")
    assert cancelled is True

    # Second call: already signaled → False (idempotency contract).
    assert await runtime.cancel("run-x") is False

    await drain_task

    types = [type(e).__name__ for e in events]
    assert "RunStartEvent" in types
    assert "ErrorEvent" in types
    # The natural last event (RunEndEvent) must NOT have fired.
    assert "RunEndEvent" not in types

    # The error event carries the cancelled marker.
    err = next(e for e in events if type(e).__name__ == "ErrorEvent")
    assert err.details.get("cancelled") is True
