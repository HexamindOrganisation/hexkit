"""Folder CRUD + ownership isolation."""

from __future__ import annotations

from httpx import AsyncClient

from ._helpers import signup


async def test_folder_crud_round_trip(client: AsyncClient) -> None:
    me = await signup(client)
    h = me["headers"]

    # empty list
    r = await client.get("/folders", headers=h)
    assert r.status_code == 200 and r.json() == []

    # create
    r = await client.post("/folders", json={"name": "work"}, headers=h)
    assert r.status_code == 201
    folder = r.json()
    assert folder["name"] == "work"
    fid = folder["id"]

    # list
    r = await client.get("/folders", headers=h)
    assert r.status_code == 200
    assert [f["id"] for f in r.json()] == [fid]

    # patch
    r = await client.patch(f"/folders/{fid}", json={"name": "renamed"}, headers=h)
    assert r.status_code == 200
    assert r.json()["name"] == "renamed"

    # delete
    r = await client.delete(f"/folders/{fid}", headers=h)
    assert r.status_code == 204

    r = await client.get("/folders", headers=h)
    assert r.json() == []


async def test_folder_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/folders")).status_code == 401
    assert (await client.post("/folders", json={"name": "x"})).status_code == 401


async def test_folder_validation(client: AsyncClient) -> None:
    h = (await signup(client))["headers"]
    r = await client.post("/folders", json={"name": ""}, headers=h)
    assert r.status_code == 422


async def test_other_users_folder_is_404(client: AsyncClient) -> None:
    alice = await signup(client, email="alice@x.io")
    bob = await signup(client, email="bob@x.io")

    r = await client.post("/folders", json={"name": "alice's"}, headers=alice["headers"])
    fid = r.json()["id"]

    # Bob can't see it...
    r = await client.get("/folders", headers=bob["headers"])
    assert r.json() == []
    # ...patch it...
    r = await client.patch(f"/folders/{fid}", json={"name": "hijacked"}, headers=bob["headers"])
    assert r.status_code == 404
    # ...or delete it.
    r = await client.delete(f"/folders/{fid}", headers=bob["headers"])
    assert r.status_code == 404
