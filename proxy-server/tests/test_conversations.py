"""Conversation CRUD + folder-move semantics + ownership isolation."""

from __future__ import annotations

from httpx import AsyncClient

from ._helpers import signup


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
