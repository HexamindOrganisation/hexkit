"""GET /me + PATCH /me — the authenticated user's profile.

PATCH lets users set their display ``name`` and an opaque ``role`` string
(which is forwarded to hexgate-wrapped agents as ``context.user.role``).
HexUI never interprets the role; it's free text per the dev team's policy
vocabulary.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import current_user
from ..db import get_session
from ..models.user import User
from ..schemas.auth import MeUpdate, UserOut

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: MeUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    """Patch the caller's profile. Only the keys provided in the request are
    written; empty strings are normalized to ``None`` so a blank text input
    clears the field rather than storing ``""``."""
    payload = body.model_dump(exclude_unset=True)
    if "name" in payload:
        value = payload["name"]
        user.name = value.strip() if isinstance(value, str) and value.strip() else None
    if "role" in payload:
        value = payload["role"]
        user.role = value.strip() if isinstance(value, str) and value.strip() else None
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)
