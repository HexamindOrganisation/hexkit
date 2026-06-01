"""POST /auth/signup and POST /auth/login.

Both routes return a fresh access token + the user record. The login path
runs the hasher unconditionally on a dummy hash when the email is unknown so
the wall-clock time of "unknown email" and "wrong password" matches — small
timing-attack mitigation worth its tiny cost.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.jwt import issue_token
from ..auth.passwords import hash_password, verify_password
from ..db import get_session
from ..models.user import User
from ..schemas.auth import Credentials, TokenOut, UserOut


router = APIRouter(prefix="/auth", tags=["auth"])

# Pre-computed hash of a throwaway password, used to keep login timing
# constant when the email is unknown.
_DUMMY_HASH = hash_password("dummy-password-for-timing-only")


def _token_response(user: User) -> TokenOut:
    return TokenOut(
        access_token=issue_token(user.id),
        user=UserOut.model_validate(user),
    )


@router.post("/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def signup(
    body: Credentials,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        # Email already taken. Reveal that explicitly — front-end needs
        # to differentiate from a generic 400, and the email being taken
        # is observable anyway via login attempts.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email already registered"
        ) from e
    await session.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenOut)
async def login(
    body: Credentials,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    result = await session.execute(
        select(User).where(User.email == body.email.lower())
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Burn the same time we would on a real verify so unknown-email
        # and wrong-password are indistinguishable from the outside.
        verify_password(body.password, _DUMMY_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
        )

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
        )

    return _token_response(user)
