"""Pre-seed demo user accounts from a YAML file.

Loaded once on startup when ``settings.demo_users_file`` is set. The intent
is to make demoing the hexgate audit pipeline trivial: instead of asking the
demo presenter to sign up Alice / Bob / Carol manually, ship a checked-in
``demo-users.yaml`` with their (throwaway) credentials and let the proxy
upsert them on boot.

Idempotent: rows are matched by email; existing rows are LEFT ALONE so
re-running with a modified file is safe — but also means a password change
in the file doesn't propagate to the DB. Wipe the DB to start fresh.

File shape::

    users:
      - email: alice@demo.local
        password: hexademo
        name: Alice Anderson
        role: billing     # optional, opaque, hexgate-only meaning
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select

from ..db import session_factory
from ..models.user import User
from .passwords import hash_password

logger = logging.getLogger("platform_backend.demo_users")


class DemoUsersError(Exception):
    """Raised when the demo users file is unreadable or malformed. Fail loud:
    a silent skip on a misconfigured demo would be confusing."""


def _load_yaml(path: Path) -> list[dict[str, Any]]:
    try:
        raw = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as e:
        raise DemoUsersError(f"failed to read {path}: {e}") from e
    if not isinstance(raw, dict) or "users" not in raw:
        raise DemoUsersError(
            f"{path}: expected a top-level mapping with a `users` key"
        )
    users = raw["users"]
    if not isinstance(users, list):
        raise DemoUsersError(f"{path}: `users` must be a list")
    return users


def _validate_entry(entry: Any, index: int) -> tuple[str, str, str | None, str | None]:
    if not isinstance(entry, dict):
        raise DemoUsersError(f"users[{index}] must be a mapping")
    email = entry.get("email")
    password = entry.get("password")
    if not isinstance(email, str) or not email:
        raise DemoUsersError(f"users[{index}]: missing or non-string `email`")
    if not isinstance(password, str) or len(password) < 8:
        raise DemoUsersError(
            f"users[{index}] ({email}): password missing or shorter than 8 chars"
        )
    name = entry.get("name")
    role = entry.get("role")
    if name is not None and not isinstance(name, str):
        raise DemoUsersError(f"users[{index}] ({email}): `name` must be a string or null")
    if role is not None and not isinstance(role, str):
        raise DemoUsersError(f"users[{index}] ({email}): `role` must be a string or null")
    return email.lower(), password, name, role


async def load_demo_users(path: Path) -> int:
    """Read ``path`` and upsert each user. Returns the number of new rows
    inserted (existing rows by email are left alone)."""
    entries = _load_yaml(path)
    inserted = 0
    async with session_factory()() as session:
        for i, entry in enumerate(entries):
            email, password, name, role = _validate_entry(entry, i)
            existing = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if existing is not None:
                continue
            session.add(
                User(
                    email=email,
                    password_hash=hash_password(password),
                    name=name,
                    role=role,
                )
            )
            inserted += 1
        await session.commit()
    if inserted:
        logger.info("seeded %d demo user(s) from %s", inserted, path)
    return inserted
