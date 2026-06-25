"""Conversation CRUD + folder-move semantics + ownership isolation."""

from __future__ import annotations

import json

import httpx
import pytest
from httpx import AsyncClient
from platform_backend import runtime_client

from ._helpers import signup


@pytest.fixture
def capture_runtime():
    """Install a mock runtime client recording every request. The test picks the
    reply via ``state["response"]`` (default ``200 {forgotten: true}``) so we can
    drive both the happy path and a backend failure without a live agent-server."""
    state: dict = {
        "requests": [],
        "response": httpx.Response(200, json={"forgotten": True}),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(
            {"method": request.method, "path": request.url.path, "body": request.content}
        )
        return state["response"]

    transport = httpx.MockTransport(handler)
    runtime_client.set_client(
        httpx.AsyncClient(base_url="http://runtime", transport=transport)
    )
    yield state
    runtime_client._client = None


async def test_conversation_crud(client: AsyncClient) -> None:
    h = (await signup(client))["headers"]

    # create
    r = await client.post(
        "/conversations",
        json={"agent_id": "langchain-hello"},
        headers=h,
    )
    assert r.status_code == 201
    conv = r.json()
    assert conv["agent_id"] == "langchain-hello"
    assert conv["title"] is None
    assert conv["folder_id"] is None
    cid = conv["id"]

    # list
    r = await client.get("/conversations", headers=h)
    assert r.status_code == 200
    assert [c["id"] for c in r.json()] == [cid]

    # rename
    r = await client.patch(f"/conversations/{cid}", json={"title": "Test chat"}, headers=h)
    assert r.status_code == 200
    assert r.json()["title"] == "Test chat"

    # delete
    r = await client.delete(f"/conversations/{cid}", headers=h)
    assert r.status_code == 204
    r = await client.get("/conversations", headers=h)
    assert r.json() == []


async def test_delete_conversation_tells_agent_to_forget(
    client: AsyncClient, capture_runtime: dict
) -> None:
    """Deleting a conversation forwards a single `POST /agents/{id}/forget` with
    the conversation id — the agent owns the memory (CONTRACT §5)."""
    h = (await signup(client))["headers"]
    cid = (
        await client.post("/conversations", json={"agent_id": "probe"}, headers=h)
    ).json()["id"]

    r = await client.delete(f"/conversations/{cid}", headers=h)
    assert r.status_code == 204

    forgets = [
        req for req in capture_runtime["requests"] if req["path"] == "/agents/probe/forget"
    ]
    assert len(forgets) == 1
    assert forgets[0]["method"] == "POST"
    assert json.loads(forgets[0]["body"]) == {"conversation_id": cid}


async def test_delete_succeeds_even_if_forget_fails(
    client: AsyncClient, capture_runtime: dict
) -> None:
    """Forget is best-effort: a backend that's down or 500s must not roll back
    the proxy-side delete (CONTRACT §5)."""
    capture_runtime["response"] = httpx.Response(500, text="backend down")
    h = (await signup(client))["headers"]
    cid = (
        await client.post("/conversations", json={"agent_id": "probe"}, headers=h)
    ).json()["id"]

    r = await client.delete(f"/conversations/{cid}", headers=h)
    assert r.status_code == 204  # delete still committed despite the failed forget

    # The conversation really is gone on the proxy side.
    assert (await client.get("/conversations", headers=h)).json() == []
    # ...and we did at least attempt the forget.
    assert any(
        req["path"] == "/agents/probe/forget" for req in capture_runtime["requests"]
    )


async def test_create_in_folder(client: AsyncClient) -> None:
    h = (await signup(client))["headers"]

    f = await client.post("/folders", json={"name": "Work"}, headers=h)
    fid = f.json()["id"]

    r = await client.post(
        "/conversations",
        json={"agent_id": "a", "folder_id": fid},
        headers=h,
    )
    assert r.status_code == 201
    assert r.json()["folder_id"] == fid


async def test_create_in_nonexistent_folder_is_404(client: AsyncClient) -> None:
    h = (await signup(client))["headers"]
    r = await client.post(
        "/conversations",
        json={"agent_id": "a", "folder_id": "00000000-0000-0000-0000-000000000000"},
        headers=h,
    )
    assert r.status_code == 404


async def test_create_in_other_users_folder_is_404(client: AsyncClient) -> None:
    alice = await signup(client, email="alice@x.io")
    bob = await signup(client, email="bob@x.io")

    f = await client.post("/folders", json={"name": "alice"}, headers=alice["headers"])
    fid = f.json()["id"]

    r = await client.post(
        "/conversations",
        json={"agent_id": "a", "folder_id": fid},
        headers=bob["headers"],
    )
    assert r.status_code == 404


async def test_patch_clear_folder(client: AsyncClient) -> None:
    h = (await signup(client))["headers"]
    f = await client.post("/folders", json={"name": "F"}, headers=h)
    fid = f.json()["id"]
    c = await client.post(
        "/conversations", json={"agent_id": "a", "folder_id": fid}, headers=h
    )
    cid = c.json()["id"]

    r = await client.patch(
        f"/conversations/{cid}", json={"clear_folder": True}, headers=h
    )
    assert r.status_code == 200
    assert r.json()["folder_id"] is None


async def test_deleting_folder_moves_conversations_to_root(client: AsyncClient) -> None:
    h = (await signup(client))["headers"]
    f = await client.post("/folders", json={"name": "F"}, headers=h)
    fid = f.json()["id"]
    c = await client.post(
        "/conversations", json={"agent_id": "a", "folder_id": fid}, headers=h
    )
    cid = c.json()["id"]

    r = await client.delete(f"/folders/{fid}", headers=h)
    assert r.status_code == 204

    r = await client.get("/conversations", headers=h)
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["id"] == cid
    assert rows[0]["folder_id"] is None


async def test_other_users_conversation_is_404(client: AsyncClient) -> None:
    alice = await signup(client, email="alice@x.io")
    bob = await signup(client, email="bob@x.io")

    c = await client.post(
        "/conversations", json={"agent_id": "a"}, headers=alice["headers"]
    )
    cid = c.json()["id"]

    assert (
        await client.patch(
            f"/conversations/{cid}", json={"title": "x"}, headers=bob["headers"]
        )
    ).status_code == 404
    assert (
        await client.delete(f"/conversations/{cid}", headers=bob["headers"])
    ).status_code == 404
    assert (
        await client.get(f"/conversations/{cid}/messages", headers=bob["headers"])
    ).status_code == 404
