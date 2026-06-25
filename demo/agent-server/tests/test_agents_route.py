"""Route-level tests for the conversation-memory behaviour added with the
Postgres removal: the stream route owns memory (appends the new turn, replays
the full transcript to the agent, records the reply), and the new
``POST /agents/{id}/forget`` clears it (CONTRACT §5).

We drive the real ASGI app through httpx; one test swaps in a recording agent so
we can assert exactly what ``input.messages`` the agent receives.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from agent_server import memory, protocol
from agent_server.routes import agents as agents_route
from agent_server.server.app import create_app
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _clean_store():
    memory._store.clear()
    yield
    memory._store.clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class _RecordingAgent:
    """A native agent that records the ``input`` it's handed and emits one text
    chunk (so the route has an assistant reply to record into memory)."""

    framework = "native"

    def __init__(self, captured: list[dict]) -> None:
        self._captured = captured

    async def run(self, *, input: dict[str, Any], context: dict[str, Any]) -> AsyncIterator[dict]:
        self._captured.append(input)
        yield protocol.text("reply ")
        yield protocol.text("text")


async def _drain_stream(client: AsyncClient, agent_id: str, body: dict) -> int:
    """POST a stream and consume it to completion (so the route's ``finally``
    block — which records the assistant reply — runs). Returns the status code."""
    async with client.stream("POST", f"/agents/{agent_id}/stream", json=body) as resp:
        if resp.status_code == 200:
            async for _ in resp.aiter_bytes():
                pass
        return resp.status_code


async def test_stream_replays_full_transcript_and_records_reply(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[dict] = []
    monkeypatch.setattr(
        agents_route, "select_agent", lambda agent_id, context: _RecordingAgent(captured)
    )

    ctx = {"conversation_id": "conv-1"}

    # Turn 1: agent sees only the new turn; memory now holds user + assistant.
    assert (
        await _drain_stream(
            client,
            "probe",
            {"input": {"messages": [{"role": "user", "content": "first"}]}, "context": ctx},
        )
        == 200
    )
    assert captured[0]["messages"] == [{"role": "user", "content": "first"}]
    assert memory.history("conv-1") == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply text"},
    ]

    # Turn 2: the agent is handed the FULL reconstructed transcript, not just the
    # new turn — this is the memory the proxy no longer sends.
    assert (
        await _drain_stream(
            client,
            "probe",
            {"input": {"messages": [{"role": "user", "content": "second"}]}, "context": ctx},
        )
        == 200
    )
    assert captured[1]["messages"] == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply text"},
        {"role": "user", "content": "second"},
    ]


async def test_stream_unknown_agent_is_404(client: AsyncClient) -> None:
    assert await _drain_stream(client, "no-such-agent", {"input": {"messages": []}}) == 404


async def test_forget_clears_memory(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        agents_route, "select_agent", lambda agent_id, context: _RecordingAgent([])
    )
    await _drain_stream(
        client,
        "probe",
        {
            "input": {"messages": [{"role": "user", "content": "hi"}]},
            "context": {"conversation_id": "conv-9"},
        },
    )
    assert memory.history("conv-9")  # populated by the run above

    r = await client.post("/agents/probe/forget", json={"conversation_id": "conv-9"})
    assert r.status_code == 200
    assert r.json() == {"forgotten": True}
    assert memory.history("conv-9") == []


async def test_forget_unknown_conversation_is_200_false(client: AsyncClient) -> None:
    """Idempotent: forgetting an id we never stored is still 200 (CONTRACT §5)."""
    r = await client.post("/agents/probe/forget", json={"conversation_id": "never-seen"})
    assert r.status_code == 200
    assert r.json() == {"forgotten": False}


async def test_forget_unknown_agent_is_404(client: AsyncClient) -> None:
    r = await client.post("/agents/no-such-agent/forget", json={"conversation_id": "x"})
    assert r.status_code == 404
