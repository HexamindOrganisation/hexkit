"""Auth round-trips: signup, login, /me with bearer."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


CREDS = {"email": "alice@example.com", "password": "hunter2hunter2"}


async def test_signup_returns_token_and_user(client: AsyncClient) -> None:
    r = await client.post("/auth/signup", json=CREDS)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == CREDS["email"]
    assert "id" in body["user"]
    assert "created_at" in body["user"]


async def test_signup_email_collision_is_409(client: AsyncClient) -> None:
    r = await client.post("/auth/signup", json=CREDS)
    assert r.status_code == 201
    r = await client.post("/auth/signup", json=CREDS)
    assert r.status_code == 409


@pytest.mark.parametrize(
    "bad",
    [
        {"email": "not-an-email", "password": "longenoughpw"},
        {"email": "ok@x.io", "password": "short"},  # < 8 chars
        {"email": "ok@x.io"},  # missing password
    ],
)
async def test_signup_validation_rejects_bad_input(
    client: AsyncClient, bad: dict
) -> None:
    r = await client.post("/auth/signup", json=bad)
    assert r.status_code == 422


async def test_signup_normalizes_email_case(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/signup", json={**CREDS, "email": "Alice@Example.COM"}
    )
    assert r.status_code == 201
    # Collision check against the same email in lowercase form.
    r = await client.post("/auth/signup", json={**CREDS, "email": "alice@example.com"})
    assert r.status_code == 409


async def test_login_succeeds_with_correct_password(client: AsyncClient) -> None:
    await client.post("/auth/signup", json=CREDS)
    r = await client.post("/auth/login", json=CREDS)
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["user"]["email"] == CREDS["email"]


async def test_login_unknown_email_is_401(client: AsyncClient) -> None:
    r = await client.post("/auth/login", json=CREDS)
    assert r.status_code == 401


async def test_login_wrong_password_is_401(client: AsyncClient) -> None:
    await client.post("/auth/signup", json=CREDS)
    r = await client.post(
        "/auth/login", json={**CREDS, "password": "wrongwrong"}
    )
    assert r.status_code == 401
