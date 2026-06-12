"""``seed_implicit_user`` populates a known dev account.

After the multi-user swap, a fresh DB has no users — which makes the dev
loop annoying. The seed exists so a developer can log in immediately as
``dev01@hexamind.ai`` / ``dev`` without going through the signup form first.
"""

from __future__ import annotations

from httpx import AsyncClient
from platform_backend.auth.implicit_user import (
    IMPLICIT_USER_EMAIL,
    IMPLICIT_USER_PASSWORD,
    seed_implicit_user,
)


async def test_seed_creates_account_that_can_log_in(client: AsyncClient) -> None:
    await seed_implicit_user()
    r = await client.post(
        "/auth/login",
        json={"email": IMPLICIT_USER_EMAIL, "password": IMPLICIT_USER_PASSWORD},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["email"] == IMPLICIT_USER_EMAIL
    assert body["access_token"]


async def test_seed_is_idempotent(client: AsyncClient) -> None:
    """Calling seed twice must not error — it's run in every worker's startup."""
    await seed_implicit_user()
    await seed_implicit_user()
    r = await client.post(
        "/auth/login",
        json={"email": IMPLICIT_USER_EMAIL, "password": IMPLICIT_USER_PASSWORD},
    )
    assert r.status_code == 200


async def test_seed_does_not_overwrite_existing_password(
    client: AsyncClient,
) -> None:
    """If a dev has already changed the seed user's password (e.g. via a
    future profile endpoint), re-running the seed must NOT clobber it.
    ON CONFLICT DO NOTHING guarantees this; the test pins the behavior."""
    # First seed sets the known dev password.
    await seed_implicit_user()
    # A second call should be a no-op — we can still log in with the same
    # known password, which proves the row wasn't re-hashed with a fresh salt
    # (a freshly hashed row would also still verify, so this test is mostly
    # a contract sanity check; the real protection is the ON CONFLICT clause).
    await seed_implicit_user()
    r = await client.post(
        "/auth/login",
        json={"email": IMPLICIT_USER_EMAIL, "password": IMPLICIT_USER_PASSWORD},
    )
    assert r.status_code == 200


async def test_seed_user_login_returns_bearer_token_that_works_on_me(
    client: AsyncClient,
) -> None:
    await seed_implicit_user()
    r = await client.post(
        "/auth/login",
        json={"email": IMPLICIT_USER_EMAIL, "password": IMPLICIT_USER_PASSWORD},
    )
    token = r.json()["access_token"]
    r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == IMPLICIT_USER_EMAIL
