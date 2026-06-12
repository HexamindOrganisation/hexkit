"""Dev-only seed for a known account.

In dev we want a fresh DB to be immediately usable — no manual signup
required. ``seed_implicit_user`` upserts a single known account on startup
(gated by ``settings.seed_dev_user``); the password ("hexademo") is hashed
with the same argon2id helper used by real signups, so login works
through the normal /auth/login path.

The route-level ``current_user`` dependency now lives in ``auth/deps.py``
and decodes a real bearer token — this module exists only for the seed.
"""

from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..db import session_factory
from ..models.user import User
from .passwords import hash_password

IMPLICIT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
IMPLICIT_USER_EMAIL = "dev01@hexamind.ai"
# Must satisfy the Credentials schema (min_length=8). Documented in QUICKSTART.md.
IMPLICIT_USER_PASSWORD = "hexademo"


async def seed_implicit_user() -> None:
    """Ensure the dev user row exists. Idempotent — uses ON CONFLICT DO NOTHING
    so existing rows (possibly with a different password) are left alone."""
    async with session_factory()() as session:
        bind = session.bind
        dialect = bind.dialect.name if bind is not None else ""
        insert_fn = pg_insert if dialect == "postgresql" else sqlite_insert
        stmt = (
            insert_fn(User)
            .values(
                id=IMPLICIT_USER_ID,
                email=IMPLICIT_USER_EMAIL,
                password_hash=hash_password(IMPLICIT_USER_PASSWORD),
            )
            .on_conflict_do_nothing(index_elements=[User.id])
        )
        await session.execute(stmt)
        await session.commit()
