"""Runtime proxy: the two read-only GETs that mirror the runtime.

Per the v1 developer contract (see ``demo/CONTRACT.md`` §2), the agent
backend exposes exactly five endpoints. Only two of them are read-only GETs
that the proxy mirrors at ``/agents`` and ``/agents/{id}/ui``; the other
three (``/stream``, ``/cancel``, ``/actions/{name}``) are exercised through
the chat route in ``test_chat.py``.

Tests use httpx's ``MockTransport`` to stand in for the runtime — no real
process spawn, no network.
"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
from httpx import AsyncClient
from platform_backend import runtime_client
from platform_backend.models.user import User
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

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


async def test_agent_allowlist_filters_roster_and_gates_routes(
    client: AsyncClient, session: AsyncSession, _mock_runtime: dict
) -> None:
    """A user with an explicit `agents` list sees only those in the roster, and
    the agent-scoped routes 403 the rest. (No list = unrestricted — that's the
    path every other test exercises.)"""
    roster = [{"id": "devops"}, {"id": "itsm"}, {"id": "healthcare"}]
    _mock_runtime["rule"] = lambda r: httpx.Response(200, json=roster)

    me = await signup(client)
    h = me["headers"]
    await session.execute(
        update(User)
        .where(User.id == uuid.UUID(me["user"]["id"]))
        .values(agents=["devops", "itsm"])
    )
    await session.commit()

    # Roster is filtered to the allow-list.
    r = await client.get("/agents", headers=h)
    assert r.status_code == 200
    assert {a["id"] for a in r.json()} == {"devops", "itsm"}

    # A disallowed agent → 403 on ui, conversation-free actions, and create.
    assert (await client.get("/agents/healthcare/ui", headers=h)).status_code == 403
    assert (
        await client.post("/agents/healthcare/actions/x", json={"args": {}}, headers=h)
    ).status_code == 403
    assert (
        await client.post("/conversations", json={"agent_id": "healthcare"}, headers=h)
    ).status_code == 403

    # An allowed agent still works.
    assert (
        await client.post("/conversations", json={"agent_id": "devops"}, headers=h)
    ).status_code == 201


async def test_proxy_requires_auth(client: AsyncClient, _mock_runtime: dict) -> None:
    """Both proxy GETs sit behind JWT."""
    for path in ("/agents", "/agents/a/ui"):
        r = await client.get(path)
        assert r.status_code == 401, f"{path} should require auth"


async def test_runtime_client_cancel_helper(_mock_runtime: dict) -> None:
    """``runtime_client.cancel`` POSTs to ``/agents/{id}/cancel`` with the
    run id in the body — the contract specified in CONTRACT.md §2."""
    _mock_runtime["rule"] = lambda r: httpx.Response(
        200, json={"cancelled": True}
    )
    assert await runtime_client.cancel("a", "r1") == {"cancelled": True}
    sent = _mock_runtime["request"]
    assert sent.url.path == "/agents/a/cancel"
    assert sent.method == "POST"
    assert json.loads(sent.content) == {"run_id": "r1"}


async def test_runtime_client_invoke_action_helper(_mock_runtime: dict) -> None:
    """``runtime_client.invoke_action`` POSTs to
    ``/agents/{id}/actions/{name}`` with ``{args}`` and returns
    ``(status, body)``."""
    _mock_runtime["rule"] = lambda r: httpx.Response(200, json={"result": "ok"})
    status, body = await runtime_client.invoke_action("a", "ping", {"x": 1})
    assert status == 200 and body == {"result": "ok"}
    sent = _mock_runtime["request"]
    assert sent.url.path == "/agents/a/actions/ping"
    assert json.loads(sent.content) == {"args": {"x": 1}}
