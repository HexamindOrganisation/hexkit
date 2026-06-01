"""Runtime proxy: 5 read-only GETs that mirror the runtime.

Tests use httpx's `MockTransport` to stand in for the runtime — no real
process spawn, no network. Subprocess-real-runtime testing lives in the
chat tests (Phase C.6, `@pytest.mark.runtime`).
"""

from __future__ import annotations

import json

import httpx
import pytest
from httpx import AsyncClient

from platform_backend import runtime_client

from ._helpers import signup


@pytest.fixture(autouse=True)
def _mock_runtime():
    """Install a MockTransport-backed AsyncClient as the runtime client.

    Each test's handler decides what the runtime returns. Restoring the
    real init at teardown isn't necessary — the next test re-installs its
    own mock via this autouse fixture.
    """
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        rule = captured.get("rule")
        if rule is None:
            return httpx.Response(500, text="no rule configured")
        return rule(request)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(base_url="http://runtime", transport=transport)
    runtime_client.set_client(client)

    yield captured


async def test_list_agents(client: AsyncClient, _mock_runtime: dict) -> None:
    payload = [{"agent_id": "a1", "name": "A1", "framework": "langchain"}]
    _mock_runtime["rule"] = lambda r: httpx.Response(200, json=payload)

    h = (await signup(client))["headers"]
    r = await client.get("/agents", headers=h)
    assert r.status_code == 200
    assert r.json() == payload
    assert _mock_runtime["request"].url.path == "/agents"


async def test_metadata_404_preserved(client: AsyncClient, _mock_runtime: dict) -> None:
    _mock_runtime["rule"] = lambda r: httpx.Response(404, json={"detail": "no such agent"})
    h = (await signup(client))["headers"]
    r = await client.get("/agents/ghost/metadata", headers=h)
    assert r.status_code == 404
    assert r.json() == {"detail": "no such agent"}


async def test_metadata_200(client: AsyncClient, _mock_runtime: dict) -> None:
    md = {"agent_id": "a1", "name": "A1", "framework": "langchain"}
    _mock_runtime["rule"] = lambda r: httpx.Response(200, json=md)
    h = (await signup(client))["headers"]
    r = await client.get("/agents/a1/metadata", headers=h)
    assert r.status_code == 200 and r.json() == md
    assert _mock_runtime["request"].url.path == "/agents/a1/metadata"


async def test_tools(client: AsyncClient, _mock_runtime: dict) -> None:
    _mock_runtime["rule"] = lambda r: httpx.Response(200, json=[{"name": "echo"}])
    h = (await signup(client))["headers"]
    r = await client.get("/agents/a1/tools", headers=h)
    assert r.status_code == 200 and r.json() == [{"name": "echo"}]


async def test_health(client: AsyncClient, _mock_runtime: dict) -> None:
    _mock_runtime["rule"] = lambda r: httpx.Response(503, json={"ok": False, "details": {"err": "no key"}})
    h = (await signup(client))["headers"]
    r = await client.get("/agents/a1/health", headers=h)
    assert r.status_code == 503
    assert r.json()["ok"] is False


async def test_ui_yaml_passthrough(client: AsyncClient, _mock_runtime: dict) -> None:
    yaml_body = "page:\n  main_color: '#abc'\n"
    _mock_runtime["rule"] = lambda r: httpx.Response(
        200, text=yaml_body, headers={"content-type": "text/yaml"}
    )
    h = (await signup(client))["headers"]
    r = await client.get("/agents/a1/ui", headers=h)
    assert r.status_code == 200
    assert r.text == yaml_body
    # The proxy preserves the upstream content-type so the FE doesn't have
    # to know the body is YAML vs JSON.
    assert r.headers["content-type"].startswith("text/yaml")


async def test_ui_404_preserved(client: AsyncClient, _mock_runtime: dict) -> None:
    _mock_runtime["rule"] = lambda r: httpx.Response(404, text="not found")
    h = (await signup(client))["headers"]
    r = await client.get("/agents/a1/ui", headers=h)
    assert r.status_code == 404


async def test_proxy_requires_auth(client: AsyncClient, _mock_runtime: dict) -> None:
    """All five proxy endpoints sit behind JWT."""
    for path in (
        "/agents",
        "/agents/a/metadata",
        "/agents/a/tools",
        "/agents/a/health",
        "/agents/a/ui",
    ):
        r = await client.get(path)
        assert r.status_code == 401, f"{path} should require auth"


async def test_runtime_client_helpers_directly(_mock_runtime: dict) -> None:
    """The runtime_client module is independently useful (chat route uses
    it directly). Exercise its non-streaming helpers."""
    _mock_runtime["rule"] = lambda r: httpx.Response(
        200, json={"cancelled": True}
    )
    assert await runtime_client.cancel("a", "r1") == {"cancelled": True}
    sent = _mock_runtime["request"]
    assert sent.url.path == "/agents/a/runs/r1/cancel"
    assert sent.method == "POST"

    _mock_runtime["rule"] = lambda r: httpx.Response(
        200, json={"result": "ok", "events": []}
    )
    status, body = await runtime_client.invoke_action("a", "ping", {"x": 1})
    assert status == 200 and body == {"result": "ok", "events": []}
    assert json.loads(_mock_runtime["request"].content) == {"args": {"x": 1}}
