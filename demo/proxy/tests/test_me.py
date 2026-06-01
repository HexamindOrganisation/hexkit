"""GET /me — bearer token enforcement and identity round-trip."""

from __future__ import annotations

from httpx import AsyncClient


CREDS = {"email": "bob@example.com", "password": "hunter2hunter2"}


async def _signup(client: AsyncClient) -> str:
    r = await client.post("/auth/signup", json=CREDS)
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


async def test_me_returns_user_with_bearer(client: AsyncClient) -> None:
    token = await _signup(client)
    r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == CREDS["email"]


async def test_me_without_header_is_401(client: AsyncClient) -> None:
    r = await client.get("/me")
    assert r.status_code == 401


async def test_me_with_garbage_token_is_401(client: AsyncClient) -> None:
    r = await client.get("/me", headers={"Authorization": "Bearer nonsense"})
    assert r.status_code == 401


async def test_me_with_wrong_scheme_is_401(client: AsyncClient) -> None:
    token = await _signup(client)
    r = await client.get("/me", headers={"Authorization": f"Basic {token}"})
    assert r.status_code == 401


async def test_login_token_also_works_on_me(client: AsyncClient) -> None:
    await _signup(client)
    r = await client.post("/auth/login", json=CREDS)
    token = r.json()["access_token"]
    r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
