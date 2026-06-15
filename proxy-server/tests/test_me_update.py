"""PATCH /me — updating display name and role.

Both fields are optional, free-text, and overlayed onto the existing user
row. Empty strings are normalized to None so a blank input clears the value.
"""

from __future__ import annotations

from httpx import AsyncClient

from ._helpers import signup


async def test_patch_sets_name_and_role(client: AsyncClient) -> None:
    me = await signup(client)
    r = await client.patch(
        "/me",
        json={"name": "Alice Anderson", "role": "billing"},
        headers=me["headers"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Alice Anderson"
    assert body["role"] == "billing"


async def test_patch_partial_only_writes_provided_keys(client: AsyncClient) -> None:
    me = await signup(client)
    # Set both first.
    await client.patch(
        "/me",
        json={"name": "Alice", "role": "billing"},
        headers=me["headers"],
    )
    # Patch only the role. Name must survive.
    r = await client.patch(
        "/me", json={"role": "support"}, headers=me["headers"]
    )
    assert r.status_code == 200
    assert r.json() == {**r.json(), "name": "Alice", "role": "support"}


async def test_patch_empty_string_clears_field(client: AsyncClient) -> None:
    me = await signup(client)
    await client.patch(
        "/me",
        json={"name": "Alice", "role": "billing"},
        headers=me["headers"],
    )
    r = await client.patch("/me", json={"role": ""}, headers=me["headers"])
    assert r.status_code == 200
    assert r.json()["role"] is None
    assert r.json()["name"] == "Alice"  # unchanged


async def test_patch_explicit_null_clears_field(client: AsyncClient) -> None:
    me = await signup(client)
    await client.patch(
        "/me",
        json={"name": "Alice", "role": "billing"},
        headers=me["headers"],
    )
    r = await client.patch("/me", json={"name": None}, headers=me["headers"])
    assert r.status_code == 200
    assert r.json()["name"] is None
    assert r.json()["role"] == "billing"  # unchanged


async def test_patch_requires_auth(client: AsyncClient) -> None:
    r = await client.patch("/me", json={"name": "x"})
    assert r.status_code == 401


async def test_me_returns_name_and_role_fields(client: AsyncClient) -> None:
    """Fresh signups have null name + role; the response must still expose
    the keys so the frontend can unconditionally read them."""
    me = await signup(client)
    r = await client.get("/me", headers=me["headers"])
    assert r.status_code == 200
    body = r.json()
    assert "name" in body and body["name"] is None
    assert "role" in body and body["role"] is None
