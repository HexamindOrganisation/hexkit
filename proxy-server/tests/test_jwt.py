"""Unit tests for ``platform_backend.auth.jwt``.

These hit the pure issue/decode functions directly — they don't need the app
or the database, so they're cheap and exhaustive.
"""

from __future__ import annotations

import time
import uuid

import jwt as pyjwt
import pytest
from platform_backend.auth.jwt import (
    InvalidTokenError,
    decode_token,
    issue_token,
)
from platform_backend.config import get_settings


def test_issue_then_decode_round_trips_user_id() -> None:
    uid = uuid.uuid4()
    token = issue_token(uid)
    assert decode_token(token) == uid


def test_decode_garbage_token_raises() -> None:
    with pytest.raises(InvalidTokenError):
        decode_token("not.a.jwt")


def test_decode_empty_string_raises() -> None:
    with pytest.raises(InvalidTokenError):
        decode_token("")


def test_decode_tampered_signature_raises() -> None:
    token = issue_token(uuid.uuid4())
    # Flip a character in the middle of the signature segment — the last
    # byte of a base64url string can absorb single-bit flips via padding,
    # so target the middle for a guaranteed-different decoded signature.
    head, payload, sig = token.rsplit(".", 2)
    mid = len(sig) // 2
    bad = sig[:mid] + ("A" if sig[mid] != "A" else "B") + sig[mid + 1 :]
    with pytest.raises(InvalidTokenError):
        decode_token(f"{head}.{payload}.{bad}")


def test_decode_wrong_secret_raises() -> None:
    bogus = pyjwt.encode(
        {"sub": str(uuid.uuid4()), "iat": int(time.time()), "exp": int(time.time()) + 60},
        "an-unrelated-secret",
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError):
        decode_token(bogus)


def test_decode_expired_token_raises() -> None:
    settings = get_settings()
    payload = {
        "sub": str(uuid.uuid4()),
        "iat": int(time.time()) - 7200,
        "exp": int(time.time()) - 3600,  # expired an hour ago
    }
    token = pyjwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        decode_token(token)


def test_decode_token_with_non_uuid_sub_raises() -> None:
    settings = get_settings()
    token = pyjwt.encode(
        {"sub": "not-a-uuid", "iat": int(time.time()), "exp": int(time.time()) + 60},
        settings.jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError):
        decode_token(token)


def test_decode_token_without_sub_raises() -> None:
    settings = get_settings()
    token = pyjwt.encode(
        {"iat": int(time.time()), "exp": int(time.time()) + 60},
        settings.jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError):
        decode_token(token)


def test_decode_token_with_wrong_algorithm_raises() -> None:
    # `none` algorithm has been a real CVE source — confirm we reject it.
    token = pyjwt.encode(
        {"sub": str(uuid.uuid4()), "iat": int(time.time()), "exp": int(time.time()) + 60},
        "",
        algorithm="none",
    )
    with pytest.raises(InvalidTokenError):
        decode_token(token)


def test_issued_token_has_expected_payload_shape() -> None:
    settings = get_settings()
    uid = uuid.uuid4()
    token = issue_token(uid)
    payload = pyjwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    assert payload["sub"] == str(uid)
    assert "iat" in payload and "exp" in payload
    assert payload["exp"] - payload["iat"] == settings.jwt_expiry_seconds
