"""Shared test helpers."""

from __future__ import annotations

from httpx import AsyncClient


async def signup(client: AsyncClient, email: str = "a@x.io", password: str = "hunter2hunter2") -> dict:
    """Sign up and return `{token, user, headers}` so tests don't repeat themselves."""
    r = await client.post("/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    body = r.json()
    return {
        "token": body["access_token"],
        "user": body["user"],
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
    }
