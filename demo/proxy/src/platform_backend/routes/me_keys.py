"""Per-user API keys.

The values are encrypted at rest (Fernet) and never returned over the wire.
`GET` lists presence + last-update timestamp so the FE can render an "X is
set / not set" UI without ever seeing the secret.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.implicit_user import current_user
from ..crypto import fernet
from ..db import get_session
from ..models.api_key import ApiKey
from ..models.user import User
from ..schemas.api_key import ApiKeyIn, ApiKeyOut, Provider


router = APIRouter(prefix="/me/keys", tags=["me"])


def _upsert_stmt(session: AsyncSession):
    """Pick the right dialect-specific `INSERT ... ON CONFLICT` for upserts.

    SQLAlchemy 2.x doesn't expose a portable `on_conflict_do_update`; the
    dialect modules provide it. Postgres in production, SQLite in tests —
    both supported.
    """
    bind = session.bind
    dialect_name = bind.dialect.name if bind is not None else ""
    return pg_insert if dialect_name == "postgresql" else sqlite_insert


@router.get("", response_model=list[ApiKeyOut])
async def list_keys(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ApiKeyOut]:
    result = await session.execute(
        select(ApiKey).where(ApiKey.user_id == user.id)
    )
    return [
        ApiKeyOut(provider=k.provider, present=True, updated_at=k.updated_at)
        for k in result.scalars().all()
    ]


@router.put("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def put_key(
    provider: Provider,
    body: ApiKeyIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    ciphertext = fernet.encrypt(body.value)
    insert_fn = _upsert_stmt(session)
    stmt = insert_fn(ApiKey).values(
        user_id=user.id,
        provider=provider,
        ciphertext=ciphertext,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[ApiKey.user_id, ApiKey.provider],
        set_={"ciphertext": stmt.excluded.ciphertext},
    )
    await session.execute(stmt)
    await session.commit()


@router.delete("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    provider: Provider,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    # Idempotent: DELETE on a row that isn't there is still a 204. Lets the
    # FE call this without first checking presence.
    await session.execute(
        delete(ApiKey).where(
            ApiKey.user_id == user.id, ApiKey.provider == provider
        )
    )
    await session.commit()


# ---------------------------------------------------------------------------
# Internal — used by the chat route (Phase C.4)
# ---------------------------------------------------------------------------

async def load_credentials_dict(
    session: AsyncSession, user_id
) -> dict[str, str]:
    """Decrypt every stored key for the user and return a flat dict shaped for
    the runtime's `Credentials` model: `{"openai_api_key": ..., ...}`."""
    result = await session.execute(
        select(ApiKey).where(ApiKey.user_id == user_id)
    )
    out: dict[str, str] = {}
    for row in result.scalars().all():
        out[f"{row.provider}_api_key"] = fernet.decrypt(row.ciphertext)
    return out
