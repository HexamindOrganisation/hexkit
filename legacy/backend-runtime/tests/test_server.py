"""HTTP server: routes wired correctly against a registry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from platform_runtime.registry import AgentRegistry
from platform_runtime.server import create_app


@pytest.fixture
def client(fake_agent_dir: Path) -> TestClient:
    reg = AgentRegistry()
    reg.load(fake_agent_dir)
    app = create_app(reg)
    return TestClient(app)


def test_list_agents(client: TestClient) -> None:
    r = client.get("/agents")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["agent_id"] == "my-fake"
    assert body[0]["capabilities"]["tools"] is True


def test_metadata(client: TestClient) -> None:
    r = client.get("/agents/my-fake/metadata")
    assert r.status_code == 200
    assert r.json()["framework"] == "fake"


def test_tools(client: TestClient) -> None:
    r = client.get("/agents/my-fake/tools")
    assert r.status_code == 200
    tools = r.json()
    assert tools[0]["name"] == "echo"
    assert "text" in tools[0]["input_schema"]["properties"]


def test_health_ok(client: TestClient) -> None:
    r = client.get("/agents/my-fake/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_unknown_agent_404(client: TestClient) -> None:
    r = client.get("/agents/does-not-exist/metadata")
    assert r.status_code == 404


def test_ui_yaml_returns_404_when_absent(client: TestClient) -> None:
    """The fake agent fixture ships no ui.yaml — the endpoint must 404
    so the front-app can fall back to its default chat layout."""
    r = client.get("/agents/my-fake/ui")
    assert r.status_code == 404


def test_ui_yaml_returns_file_when_present(
    client: TestClient, fake_agent_dir: Path
) -> None:
    """When a ui.yaml exists in the agent's folder, the endpoint returns
    its bytes verbatim with `text/yaml` content type."""
    payload = "page:\n  layout_type: grid\nwidgets: []\n"
    (fake_agent_dir / "ui.yaml").write_text(payload, encoding="utf-8")
    r = client.get("/agents/my-fake/ui")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/yaml")
    assert r.text == payload


def test_invoke_returns_run_end(client: TestClient) -> None:
    r = client.post("/agents/my-fake/invoke", json={"input": "hi"})
    assert r.status_code == 200
    body = r.json()
    assert body["event_type"] == "run_end"
    assert body["output"] == {"ok": True}
    # The terminal event also carries the assembled run result.
    assert body["result"]["message"] == "Hello world"


def test_stream_sse_sequence(client: TestClient) -> None:
    """End-to-end: ordered SSE event stream with monotonic sequence."""
    with client.stream(
        "POST", "/agents/my-fake/stream", json={"input": "hi"}
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = r.read().decode()

    # Parse SSE frames into (event, data) pairs. Frames are separated by a
    # blank line; sse-starlette uses CRLF endings so we normalize first.
    normalized = body.replace("\r\n", "\n").strip()
    frames: list[tuple[str, dict]] = []
    for block in normalized.split("\n\n"):
        evt = None
        data = None
        for line in block.splitlines():
            if line.startswith("event:"):
                evt = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data = json.loads(line[len("data:"):].strip())
        if evt and data is not None:
            frames.append((evt, data))

    types = [t for t, _ in frames]
    assert types == [
        "run_start",
        "block_start",
        "block_delta",
        "block_delta",
        "block_end",
        "tool_start",
        "tool_end",
        "run_end",
    ]

    # The SSE `event:` name mirrors the payload's `event_type`.
    assert all(evt == d["event_type"] for evt, d in frames)

    # Sequence numbers are strictly increasing (persisted steps share the
    # counter, so wire events are monotonic but not contiguous).
    seqs = [d["sequence"] for _, d in frames]
    assert all(b > a for a, b in zip(seqs, seqs[1:]))

    # All events share the same run_id, and a flat run is its own root.
    run_ids = {d["run_id"] for _, d in frames}
    assert len(run_ids) == 1
    assert all(d["root_run_id"] == d["run_id"] for _, d in frames)
