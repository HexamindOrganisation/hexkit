"""Per-user API keys: encryption round-trip + presence-only `GET`."""

from __future__ import annotations

from httpx import AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_backend.crypto import fernet
from platform_backend.models.api_key import ApiKey

from ._helpers import signup


async def test_put_then_list(client: AsyncClient) -> None:
    h = (await signup(client))["headers"]

    r = await client.get("/me/keys", headers=h)
    assert r.status_code == 200 and r.json() == []

    r = await client.put("/me/keys/openai", json={"value": "sk-secret"}, headers=h)
    assert r.status_code == 204

    r = await client.get("/me/keys", headers=h)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["provider"] == "openai"
    assert rows[0]["present"] is True
    assert "updated_at" in rows[0]
    # Critical: the plaintext must never appear in the listing payload.
    assert "value" not in rows[0]
    assert "sk-secret" not in r.text


async def test_put_is_upsert(client: AsyncClient) -> None:
    h = (await signup(client))["headers"]
    await client.put("/me/keys/openai", json={"value": "sk-a"}, headers=h)
    await client.put("/me/keys/openai", json={"value": "sk-b"}, headers=h)
    r = await client.get("/me/keys", headers=h)
    assert len(r.json()) == 1  # one row, replaced not duplicated


async def test_delete_is_idempotent(client: AsyncClient) -> None:
    h = (await signup(client))["headers"]
    assert (await client.delete("/me/keys/openai", headers=h)).status_code == 204
    await client.put("/me/keys/openai", json={"value": "sk-a"}, headers=h)
    assert (await client.delete("/me/keys/openai", headers=h)).status_code == 204
    assert (await client.delete("/me/keys/openai", headers=h)).status_code == 204
    assert (await client.get("/me/keys", headers=h)).json() == []


@pytest.mark.parametrize("provider", ["openai", "anthropic", "google"])
async def test_each_supported_provider_accepted(
    client: AsyncClient, provider: str
) -> None:
    h = (await signup(client))["headers"]
    r = await client.put(f"/me/keys/{provider}", json={"value": "v"}, headers=h)
    assert r.status_code == 204


async def test_unknown_provider_is_422(client: AsyncClient) -> None:
    h = (await signup(client))["headers"]
    r = await client.put("/me/keys/cohere", json={"value": "v"}, headers=h)
    assert r.status_code == 422


async def test_empty_value_is_422(client: AsyncClient) -> None:
    h = (await signup(client))["headers"]
    r = await client.put("/me/keys/openai", json={"value": ""}, headers=h)
    assert r.status_code == 422


async def test_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/me/keys")).status_code == 401
    assert (await client.put("/me/keys/openai", json={"value": "x"})).status_code == 401
    assert (await client.delete("/me/keys/openai")).status_code == 401


async def test_one_users_key_not_visible_to_another(client: AsyncClient) -> None:
    alice = await signup(client, email="alice@x.io")
    bob = await signup(client, email="bob@x.io")
    await client.put("/me/keys/openai", json={"value": "sk-a"}, headers=alice["headers"])
    r = await client.get("/me/keys", headers=bob["headers"])
    assert r.json() == []


async def test_stored_ciphertext_is_encrypted(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Defense-in-depth: read the row straight from the DB and verify the
    column does not contain the plaintext (i.e. the route really encrypted it)."""
    h = (await signup(client))["headers"]
    await client.put("/me/keys/openai", json={"value": "sk-very-secret"}, headers=h)

    rows = (await session.execute(select(ApiKey))).scalars().all()
    assert len(rows) == 1
    assert b"sk-very-secret" not in rows[0].ciphertext
    # And the canonical decrypt round-trips.
    assert fernet.decrypt(rows[0].ciphertext) == "sk-very-secret"


async def test_load_credentials_dict_helper(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The chat route (Phase C.4) uses `load_credentials_dict`; verify it
    builds the shape the runtime's `Credentials` model expects."""
    from platform_backend.routes.me_keys import load_credentials_dict

    me = await signup(client)
    h = me["headers"]
    await client.put("/me/keys/openai", json={"value": "sk-x"}, headers=h)
    await client.put("/me/keys/anthropic", json={"value": "ant-y"}, headers=h)

    import uuid as _u
    creds = await load_credentials_dict(session, _u.UUID(me["user"]["id"]))
    assert creds == {"openai_api_key": "sk-x", "anthropic_api_key": "ant-y"}
