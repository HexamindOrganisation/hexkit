"""Smoke-test that every protected route refuses unauthenticated requests.

The implicit-user shim used to make all of these reachable without a token.
After the multi-user swap, every router that depends on ``current_user`` must
return 401 on a missing or bad bearer header — otherwise we've silently
de-authed a route.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# (method, path) pairs. Pick the cheapest endpoint per router; we only care
# that the dependency rejects before any body parsing happens.
PROTECTED_ENDPOINTS = [
    ("GET", "/me"),
    ("GET", "/files"),
    ("GET", "/folders"),
    ("GET", "/conversations"),
    ("GET", "/agents"),
]


@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
async def test_protected_route_requires_auth(
    client: AsyncClient, method: str, path: str
) -> None:
    r = await client.request(method, path)
    assert r.status_code == 401, f"{method} {path} returned {r.status_code}, expected 401"


@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
async def test_protected_route_rejects_garbage_token(
    client: AsyncClient, method: str, path: str
) -> None:
    r = await client.request(
        method, path, headers={"Authorization": "Bearer nonsense.token.here"}
    )
    assert r.status_code == 401


async def test_protected_route_rejects_wrong_scheme(client: AsyncClient) -> None:
    # Even a valid-looking token under the wrong scheme must 401.
    r = await client.post(
        "/auth/signup",
        json={"email": "x@x.io", "password": "hunter2hunter2"},
    )
    token = r.json()["access_token"]
    r = await client.get("/me", headers={"Authorization": f"Basic {token}"})
    assert r.status_code == 401


async def test_401_includes_www_authenticate_header(client: AsyncClient) -> None:
    """RFC 6750 says 401 from a bearer-protected resource must advertise the
    scheme. The frontend doesn't rely on it, but standards-conformance is cheap."""
    r = await client.get("/me")
    assert r.status_code == 401
    assert r.headers.get("WWW-Authenticate", "").lower().startswith("bearer")
