"""Single-user stand-in for the JWT ``current_user`` dependency.

v1 of HexaUI is single-user: there is exactly one implicit account, and every
authenticated route resolves to it. The route bodies are unchanged — they still
filter persistence by ``user.id`` — so multi-user can return later by swapping
this dependency back for the JWT one in ``auth/deps.py`` (left on disk, unwired).

The user row is seeded idempotently at startup (see ``server/app.py`` lifespan);
``current_user`` also seeds on miss so routes work in tests that hit them
directly without the lifespan.
"""

from __future__ import annotations

import uuid

from fastapi import Depends
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session, session_factory
from ..models.user import User

IMPLICIT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
IMPLICIT_USER_EMAIL = "dev01@hexamind.ai"


async def seed_implicit_user() -> None:
    """Ensure the single implicit user row exists. Idempotent and safe to call
    from every worker's startup (``ON CONFLICT DO NOTHING``)."""
    async with session_factory()() as session:
        bind = session.bind
        dialect = bind.dialect.name if bind is not None else ""
        insert_fn = pg_insert if dialect == "postgresql" else sqlite_insert
        stmt = (
            insert_fn(User)
            .values(
                id=IMPLICIT_USER_ID,
                email=IMPLICIT_USER_EMAIL,
                password_hash="",
            )
            .on_conflict_do_nothing(index_elements=[User.id])
        )
        await session.execute(stmt)
        await session.commit()


async def current_user(
    session: AsyncSession = Depends(get_session),
) -> User:
    user = await session.get(User, IMPLICIT_USER_ID)
    if user is None:
        await seed_implicit_user()
        user = await session.get(User, IMPLICIT_USER_ID)
    return user
