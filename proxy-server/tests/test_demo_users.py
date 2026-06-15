"""The demo-users YAML loader.

Verifies upsert + idempotency, plus the validation errors a malformed file
should raise. The loader is opt-in via ``PLATFORM_DEMO_USERS_FILE``; these
tests call ``load_demo_users(path)`` directly so they don't depend on env.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from platform_backend.auth.demo_users import DemoUsersError, load_demo_users


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "demo-users.yaml"
    p.write_text(body)
    return p


async def test_loader_inserts_users(tmp_path: Path, client: AsyncClient) -> None:
    path = _write(
        tmp_path,
        """
        users:
          - email: alice@example.com
            password: hexademo
            name: Alice
            role: billing
          - email: bob@example.com
            password: hexademo
            name: Bob
        """,
    )
    n = await load_demo_users(path)
    assert n == 2

    # Alice can log in and her profile carries name + role.
    r = await client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "hexademo"},
    )
    assert r.status_code == 200
    assert r.json()["user"]["name"] == "Alice"
    assert r.json()["user"]["role"] == "billing"

    # Bob with no role specified has role=null.
    r = await client.post(
        "/auth/login",
        json={"email": "bob@example.com", "password": "hexademo"},
    )
    assert r.status_code == 200
    assert r.json()["user"]["role"] is None


async def test_loader_is_idempotent(tmp_path: Path, client: AsyncClient) -> None:
    path = _write(
        tmp_path,
        """
        users:
          - email: alice@example.com
            password: hexademo
            name: Alice
        """,
    )
    assert await load_demo_users(path) == 1
    assert await load_demo_users(path) == 0  # second call is a no-op

    # Login still works after the second call (row wasn't clobbered).
    r = await client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "hexademo"},
    )
    assert r.status_code == 200


async def test_loader_does_not_overwrite_existing_password(
    tmp_path: Path, client: AsyncClient
) -> None:
    """If a user already exists (via signup or a prior load), changing the
    file's password and re-running must NOT silently change the live password."""
    # First load with password "hexademo".
    path = _write(
        tmp_path,
        """
        users:
          - email: alice@example.com
            password: hexademo
            name: Alice
        """,
    )
    await load_demo_users(path)

    # Second load with a different password.
    path.write_text(
        """
        users:
          - email: alice@example.com
            password: totally-different-pw
            name: Alice Anderson
        """
    )
    assert await load_demo_users(path) == 0  # nothing inserted

    # Original password still works; the new one does not.
    r = await client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "hexademo"},
    )
    assert r.status_code == 200
    r = await client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "totally-different-pw"},
    )
    assert r.status_code == 401


async def test_loader_rejects_missing_users_key(tmp_path: Path) -> None:
    path = _write(tmp_path, "{}")
    with pytest.raises(DemoUsersError, match="users"):
        await load_demo_users(path)


async def test_loader_rejects_short_password(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
        users:
          - email: x@y.z
            password: short
        """,
    )
    with pytest.raises(DemoUsersError, match="shorter than 8"):
        await load_demo_users(path)


async def test_loader_rejects_missing_email(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
        users:
          - password: hexademo
        """,
    )
    with pytest.raises(DemoUsersError, match="email"):
        await load_demo_users(path)


async def test_loader_lowercases_email_for_dedup(
    tmp_path: Path, client: AsyncClient
) -> None:
    """Email casing differences in the file should not create duplicates: the
    loader matches existing rows case-insensitively because signups lower-case
    email at write time."""
    # First sign up alice through the normal route (lowercase storage).
    r = await client.post(
        "/auth/signup",
        json={"email": "alice@example.com", "password": "hexademo"},
    )
    assert r.status_code == 201

    # Now load a YAML referring to the same email in mixed case.
    path = _write(
        tmp_path,
        """
        users:
          - email: Alice@Example.COM
            password: hexademo
            name: Alice
        """,
    )
    assert await load_demo_users(path) == 0  # matched, not duplicated
