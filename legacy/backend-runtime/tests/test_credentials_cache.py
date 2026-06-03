"""
`CredentialsCache` unit tests.

The cache is what makes `request.context.credentials` route to per-user
framework clients without breaking legacy agents whose factories take no
arguments. The three adapters delegate to it, so the bulk of the new
logic lives here and is worth testing in isolation.
"""

from __future__ import annotations

import pytest

from platform_runtime.adapters.credentials_cache import CredentialsCache
from platform_runtime.protocol import Credentials


# ---------------------------------------------------------------------------
# Factory shapes
# ---------------------------------------------------------------------------

class _NoCredsFactory:
    """Legacy factory — takes no args. Used by every existing example agent."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return {"id": self.calls}


class _CredsFactory:
    """New-style factory that opts in by declaring `credentials`."""

    def __init__(self) -> None:
        self.calls: list[Credentials | None] = []

    def __call__(self, credentials=None):
        self.calls.append(credentials)
        return {"id": len(self.calls), "creds": credentials}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_legacy_factory_called_once_then_cached() -> None:
    f = _NoCredsFactory()
    cache = CredentialsCache(f)
    a = await cache.get({})
    b = await cache.get({})
    assert a is b
    assert f.calls == 1


async def test_credentials_ignored_for_legacy_factory() -> None:
    """A factory that doesn't accept credentials gets called with no args even
    when context.credentials is set — the cache silently degrades."""
    f = _NoCredsFactory()
    cache = CredentialsCache(f)
    a = await cache.get({"credentials": {"openai_api_key": "sk-a"}})
    b = await cache.get({"credentials": {"openai_api_key": "sk-b"}})
    assert a is b  # both fell through to the no-creds slot
    assert f.calls == 1


async def test_creds_factory_no_credentials_in_context() -> None:
    f = _CredsFactory()
    cache = CredentialsCache(f)
    a = await cache.get({})
    assert f.calls == [None]
    # Repeat with no creds → cache hit.
    b = await cache.get({})
    assert a is b
    assert len(f.calls) == 1


async def test_creds_factory_distinguishes_different_keys() -> None:
    f = _CredsFactory()
    cache = CredentialsCache(f)
    a = await cache.get({"credentials": {"openai_api_key": "sk-a"}})
    b = await cache.get({"credentials": {"openai_api_key": "sk-b"}})
    assert a is not b
    assert len(f.calls) == 2
    assert f.calls[0].openai_api_key == "sk-a"
    assert f.calls[1].openai_api_key == "sk-b"


async def test_creds_factory_same_key_hits_cache() -> None:
    f = _CredsFactory()
    cache = CredentialsCache(f)
    a = await cache.get({"credentials": {"openai_api_key": "sk-a"}})
    b = await cache.get({"credentials": {"openai_api_key": "sk-a"}})
    assert a is b
    assert len(f.calls) == 1


async def test_empty_credentials_dict_collapses_to_none_slot() -> None:
    """{"credentials": {}} or all-None values should not produce a separate
    cache entry — they're equivalent to "no creds"."""
    f = _CredsFactory()
    cache = CredentialsCache(f)
    a = await cache.get({})
    b = await cache.get({"credentials": {}})
    c = await cache.get({"credentials": {"openai_api_key": None}})
    assert a is b is c
    assert f.calls == [None]


async def test_credentials_pydantic_instance_accepted() -> None:
    """The cache accepts either a dict or a Credentials instance — useful for
    tests that build Credentials directly."""
    f = _CredsFactory()
    cache = CredentialsCache(f)
    creds = Credentials(openai_api_key="sk-x")
    a = await cache.get({"credentials": creds})
    b = await cache.get({"credentials": {"openai_api_key": "sk-x"}})
    assert a is b


async def test_validator_runs_on_each_build() -> None:
    seen: list = []

    def validate(result) -> None:
        seen.append(result)
        if result["id"] > 1:
            raise TypeError("only id=1 allowed")

    f = _CredsFactory()
    cache = CredentialsCache(f, validator=validate)
    await cache.get({"credentials": {"openai_api_key": "sk-a"}})
    with pytest.raises(TypeError):
        await cache.get({"credentials": {"openai_api_key": "sk-b"}})
    assert len(seen) == 2


async def test_builder_postprocesses_each_factory_result() -> None:
    """The builder hook lets ADK wrap each per-credentials Agent in a Runner."""

    async def wrap(value):
        return ("wrapped", value)

    f = _CredsFactory()
    cache = CredentialsCache(f, builder=wrap)
    a = await cache.get({"credentials": {"openai_api_key": "sk-a"}})
    assert a[0] == "wrapped"
    assert a[1]["creds"].openai_api_key == "sk-a"


async def test_cache_evicts_at_capacity() -> None:
    """More than 8 distinct credential hashes evict the oldest entry."""
    f = _CredsFactory()
    cache = CredentialsCache(f)
    for i in range(9):
        await cache.get({"credentials": {"openai_api_key": f"sk-{i}"}})
    # 9 distinct keys, but the oldest (sk-0) should be gone — re-requesting
    # rebuilds it.
    await cache.get({"credentials": {"openai_api_key": "sk-0"}})
    assert len(f.calls) == 10  # 9 distinct + the rebuild


async def test_async_factory_supported() -> None:
    async def afactory(credentials=None):
        return {"creds": credentials}

    cache = CredentialsCache(afactory)
    a = await cache.get({"credentials": {"openai_api_key": "sk-x"}})
    assert a["creds"].openai_api_key == "sk-x"
