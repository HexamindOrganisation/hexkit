"""FastAPI dependency: extract+verify the bearer token, load the user row.

Every authenticated route depends on `current_user`. Failures (no header,
bad token, unknown user) all return 401 with no body distinction — leaking
which one failed is a small but free fingerprinting reduction.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models.user import User
from .jwt import InvalidTokenError, decode_token

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def _extract_bearer(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _UNAUTHORIZED
    return token


async def current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    token = _extract_bearer(request)
    try:
        user_id = decode_token(token)
    except InvalidTokenError as e:
        raise _UNAUTHORIZED from e

    user = await session.get(User, user_id)
    if user is None:
        raise _UNAUTHORIZED
    return user
