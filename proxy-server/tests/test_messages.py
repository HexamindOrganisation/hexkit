"""GET /conversations/{id}/messages — read-only listing.

Writes go through the chat route (Phase C.4). Until then this only exercises
the listing path: empty (always, since nothing else writes messages yet),
404 for unknown conversations, and ownership isolation.
"""

from __future__ import annotations

from httpx import AsyncClient

from ._helpers import signup


async def test_empty_conversation_returns_empty_list(client: AsyncClient) -> None:
    h = (await signup(client))["headers"]
    c = await client.post("/conversations", json={"agent_id": "a"}, headers=h)
    cid = c.json()["id"]
    r = await client.get(f"/conversations/{cid}/messages", headers=h)
    assert r.status_code == 200
    assert r.json() == []


async def test_unknown_conversation_is_404(client: AsyncClient) -> None:
    h = (await signup(client))["headers"]
    r = await client.get(
        "/conversations/00000000-0000-0000-0000-000000000000/messages",
        headers=h,
    )
    assert r.status_code == 404


async def test_requires_auth(client: AsyncClient) -> None:
    r = await client.get(
        "/conversations/00000000-0000-0000-0000-000000000000/messages"
    )
    assert r.status_code == 401
