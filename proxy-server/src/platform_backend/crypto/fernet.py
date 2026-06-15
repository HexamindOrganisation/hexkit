"""
Fernet wrapper for per-user API key encryption.

Fernet is symmetric AES-CBC + HMAC-SHA256 in a constant-time-safe envelope.
Good enough for v0 secret-at-rest; a future control plane can move to a
managed KMS by replacing this module behind the same `encrypt`/`decrypt`
interface — the rest of the code never touches Fernet directly.

The key is read from `PLATFORM_FERNET_KEY` (url-safe-base64 32 bytes). An
empty key fails fast on first encrypt — never silently no-op.
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from ..config import get_settings


class FernetNotConfigured(RuntimeError):
    """The Fernet master key env var is missing or malformed."""


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = get_settings().fernet_key
    if not key:
        raise FernetNotConfigured(
            "PLATFORM_FERNET_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"` and put it in `.env`."
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        raise FernetNotConfigured(f"PLATFORM_FERNET_KEY is not a valid Fernet key: {e}") from e


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    try:
        return _fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken as e:
        # Either tampered, or encrypted with a different master key. Either
        # way the secret is unrecoverable; surface it as a clear error so the
        # caller can prompt the user to re-enter the key.
        raise FernetNotConfigured(
            "Stored ciphertext could not be decrypted with the current "
            "PLATFORM_FERNET_KEY (rotated key or tampered data?)"
        ) from e


def reset_cache() -> None:
    """Clear the cached Fernet instance — used by tests when the env var
    changes mid-session."""
    _fernet.cache_clear()
