"""HS256 access-token issue + verify.

v0 has no refresh tokens. The access token carries the user id as `sub` and
expires after `Settings.jwt_expiry_seconds` (default 24h).
"""

from __future__ import annotations

import time
import uuid

import jwt as pyjwt

from ..config import get_settings

_ALGO = "HS256"


class InvalidTokenError(Exception):
    """Raised on any decode failure: expired, bad signature, malformed."""


def issue_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + settings.jwt_expiry_seconds,
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=_ALGO)


def decode_token(token: str) -> uuid.UUID:
    """Return the user id encoded in `sub`, or raise `InvalidTokenError`."""
    settings = get_settings()
    try:
        payload = pyjwt.decode(token, settings.jwt_secret, algorithms=[_ALGO])
    except pyjwt.PyJWTError as e:
        raise InvalidTokenError(str(e)) from e
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise InvalidTokenError("missing or non-string sub claim")
    try:
        return uuid.UUID(sub)
    except ValueError as e:
        raise InvalidTokenError("sub is not a UUID") from e
