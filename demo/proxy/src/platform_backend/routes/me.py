"""GET /me — return the authenticated user's profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth.deps import current_user
from ..models.user import User
from ..schemas.auth import UserOut

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.model_validate(user)
