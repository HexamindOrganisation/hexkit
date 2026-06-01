"""argon2id password hashing.

A single shared `PasswordHasher` instance with library defaults. Defaults
match the OWASP recommendation as of 2024 and produce hashes that include
all parameters, so future tuning never strands old hashes.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plaintext: str) -> str:
    return _hasher.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        _hasher.verify(hashed, plaintext)
        return True
    except VerifyMismatchError:
        return False
    except Exception:
        # Malformed hash, wrong algorithm, etc. — treat as auth failure
        # rather than crashing the request.
        return False
