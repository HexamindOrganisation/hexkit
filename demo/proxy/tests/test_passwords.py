"""Unit tests for ``platform_backend.auth.passwords``.

Wraps argon2id. We don't re-test argon2 itself — just that our thin wrapper
returns the right shape and never raises on weird input (login should treat
verify failures as "wrong password," not 500).
"""

from __future__ import annotations

from platform_backend.auth.passwords import hash_password, verify_password


def test_hash_then_verify_succeeds() -> None:
    h = hash_password("hunter2hunter2")
    assert verify_password("hunter2hunter2", h) is True


def test_verify_rejects_wrong_password() -> None:
    h = hash_password("hunter2hunter2")
    assert verify_password("not-the-password", h) is False


def test_hash_is_not_plaintext() -> None:
    plaintext = "hunter2hunter2"
    assert plaintext not in hash_password(plaintext)


def test_hash_is_salted_so_two_hashes_of_same_password_differ() -> None:
    a = hash_password("same-password")
    b = hash_password("same-password")
    assert a != b
    assert verify_password("same-password", a)
    assert verify_password("same-password", b)


def test_hash_uses_argon2id_prefix() -> None:
    # Format: $argon2id$v=19$… — a regression check in case the underlying
    # PasswordHasher defaults change to a weaker variant.
    h = hash_password("anything")
    assert h.startswith("$argon2id$")


def test_verify_returns_false_for_malformed_hash() -> None:
    # The seed code stored ``password_hash=""`` before our fix; verify must
    # not raise on that, just refuse the login.
    assert verify_password("anything", "") is False
    assert verify_password("anything", "not-a-hash") is False
    assert verify_password("anything", "$argon2id$bogus") is False
