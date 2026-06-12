"""Cross-user data isolation.

Routes filter persistence by ``user.id`` extracted from the JWT. These tests
exercise the per-user scoping at the HTTP layer so a future refactor can't
silently drop the ``WHERE user_id = …`` clause.
"""

from __future__ import annotations

from httpx import AsyncClient

from ._helpers import signup


async def test_user_b_cannot_see_user_a_conversations(client: AsyncClient) -> None:
    a = await signup(client, email="alice@example.com")
    b = await signup(client, email="bob@example.com")

    # Alice creates a conversation
    r = await client.post(
        "/conversations",
        json={"agent_id": "probe", "folder_id": None, "title": "alice-private"},
        headers=a["headers"],
    )
    assert r.status_code == 201

    # Bob's list must be empty
    r = await client.get("/conversations", headers=b["headers"])
    assert r.status_code == 200
    assert r.json() == []

    # Alice still sees hers
    r = await client.get("/conversations", headers=a["headers"])
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["title"] == "alice-private"


async def test_user_b_cannot_fetch_user_a_conversation_directly(
    client: AsyncClient,
) -> None:
    """Fetching another user's conversation must 404 — not 403 — to avoid
    leaking which ids exist."""
    a = await signup(client, email="alice@example.com")
    b = await signup(client, email="bob@example.com")

    r = await client.post(
        "/conversations",
        json={"agent_id": "probe", "folder_id": None, "title": "secret"},
        headers=a["headers"],
    )
    conv_id = r.json()["id"]

    r = await client.get(f"/conversations/{conv_id}/messages", headers=b["headers"])
    assert r.status_code == 404


async def test_user_b_cannot_delete_user_a_conversation(client: AsyncClient) -> None:
    a = await signup(client, email="alice@example.com")
    b = await signup(client, email="bob@example.com")

    r = await client.post(
        "/conversations",
        json={"agent_id": "probe", "folder_id": None, "title": "alice-keeps-this"},
        headers=a["headers"],
    )
    conv_id = r.json()["id"]

    r = await client.delete(f"/conversations/{conv_id}", headers=b["headers"])
    assert r.status_code == 404

    # And the conversation is still there for Alice.
    r = await client.get("/conversations", headers=a["headers"])
    assert len(r.json()) == 1


async def test_user_b_cannot_see_user_a_folders(client: AsyncClient) -> None:
    a = await signup(client, email="alice@example.com")
    b = await signup(client, email="bob@example.com")

    r = await client.post(
        "/folders", json={"name": "alice-folder"}, headers=a["headers"]
    )
    assert r.status_code == 201

    r = await client.get("/folders", headers=b["headers"])
    assert r.status_code == 200
    assert r.json() == []


async def test_me_returns_the_caller_not_the_first_user(client: AsyncClient) -> None:
    """Regression: with the old implicit-user shim, every /me returned the
    same hard-coded account. After the swap, /me must reflect the token's
    actual user."""
    a = await signup(client, email="alice@example.com")
    b = await signup(client, email="bob@example.com")

    r = await client.get("/me", headers=a["headers"])
    assert r.json()["email"] == "alice@example.com"

    r = await client.get("/me", headers=b["headers"])
    assert r.json()["email"] == "bob@example.com"
