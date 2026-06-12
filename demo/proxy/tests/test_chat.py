"""
Chat route: SSE passthrough, assistant persistence, auto-title, credentials
flow, plus cancel and action proxy.

We don't spawn a real runtime here — the chat route's only runtime touchpoint
is the `runtime_client` module, which we drive through `httpx.MockTransport`.
That keeps the suite fast (no subprocess, no model API key) while still
exercising the SSE frame parser, the persistence logic, and the context
assembly end to end.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_backend import runtime_client
from platform_backend.models.conversation import Conversation
from platform_backend.models.message import Message
from platform_backend.routes import chat as chat_module

from ._helpers import signup

# ---------------------------------------------------------------------------
# Mock-runtime fixture
# ---------------------------------------------------------------------------

def _native_frame(event: dict) -> bytes:
    """One upstream SSE frame: a `{framework, event}` envelope wrapping a
    framework-native event (CONTRACT.md §5). The proxy's NativeTranslator
    accepts ``{type: text, text: ...}`` and friends."""
    data = json.dumps({"framework": "native", "event": event})
    return f"id: {uuid.uuid4().hex}\ndata: {data}\n\n".encode()


def _build_run(text_chunks: list[str]) -> bytes:
    """A canonical run from the developer backend's POV: one text event per
    chunk, then EOF. The proxy synthesizes run_start/block_start/_end/run_end
    around these — that's what the assertions on the downstream stream check."""
    parts = [_native_frame({"type": "text", "text": chunk}) for chunk in text_chunks]
    parts.append(_native_frame({"type": "done"}))
    return b"".join(parts)


@pytest.fixture
def mock_runtime():
    captured: dict = {"requests": []}

    async def aiter_body(body: bytes) -> AsyncIterator[bytes]:
        # Chunk by frame so the platform's SSE parser is exercised on real
        # delimiters, not one big blob.
        for piece in body.split(b"\n\n"):
            if not piece:
                continue
            yield piece + b"\n\n"

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["requests"].append(
            {
                "method": request.method,
                "path": request.url.path,
                "body": request.content,
            }
        )
        rule = captured.get("rule")
        if rule is None:
            return httpx.Response(500, text="no rule configured")
        result = rule(request)
        if isinstance(result, httpx.Response):
            return result
        # rule returned (status, body_bytes) → streaming response
        status_code, body = result
        return httpx.Response(
            status_code,
            stream=httpx.AsyncByteStream() if not body else _BytesStream(body),
            headers={"content-type": "text/event-stream"},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(base_url="http://runtime", transport=transport)
    runtime_client.set_client(client)

    yield captured

    chat_module._active_runs.clear()


class _BytesStream(httpx.AsyncByteStream):
    """Async byte stream that yields one frame at a time."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    async def __aiter__(self):
        for piece in self._body.split(b"\n\n"):
            if not piece:
                continue
            yield piece + b"\n\n"


# ---------------------------------------------------------------------------
# Setup helper
# ---------------------------------------------------------------------------

async def _make_conv(client: AsyncClient, headers: dict, agent_id: str = "fake-1") -> str:
    r = await client.post(
        "/conversations", json={"agent_id": agent_id}, headers=headers
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_chat_streams_through_and_persists_assistant(
    client: AsyncClient, session: AsyncSession, mock_runtime: dict
) -> None:
    h = (await signup(client))["headers"]
    cid = await _make_conv(client, h)

    upstream = _build_run(["Hello", " ", "world", "!"])
    mock_runtime["rule"] = lambda r: (200, upstream)

    async with client.stream(
        "POST",
        f"/conversations/{cid}/messages",
        json={"content": "say hi"},
        headers=h,
    ) as resp:
        assert resp.status_code == 200
        body = b""
        async for chunk in resp.aiter_raw():
            body += chunk

    # Every event from the upstream SSE survives in the downstream bytes,
    # in order. Cheaper to check by data: lines.
    event_types = []
    for line in body.split(b"\n"):
        if line.startswith(b"event:"):
            event_types.append(line[len(b"event:"):].strip().decode())
    assert event_types == [
        "run_start",
        "block_start",
        "block_delta",
        "block_delta",
        "block_delta",
        "block_delta",
        "block_end",
        "run_end",
    ]

    # The runtime got an InvokeRequest with our history + run_id + context.
    runtime_req = mock_runtime["requests"][-1]
    assert runtime_req["path"] == "/agents/fake-1/stream"
    body = json.loads(runtime_req["body"])
    assert body["input"] == {"messages": [{"role": "user", "content": "say hi"}]}
    assert body["run_id"]
    assert body["context"]["conversation_id"] == cid
    # Per CONTRACT.md §5 the context payload is `{conversation_id, credentials,
    # files}` — no user_id (the developer backend shouldn't see auth identity).
    assert "user_id" not in body["context"]
    assert body["context"]["credentials"] == {}  # no keys configured

    # Assistant row exists, content is the concatenated deltas, run_id is set.
    rows = (
        await session.execute(
            select(Message).where(
                Message.conversation_id == uuid.UUID(cid),
                Message.role == "assistant",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].content == "Hello world!"
    assert rows[0].run_id == body["run_id"]


async def test_credentials_forwarded_in_context(
    client: AsyncClient, mock_runtime: dict
) -> None:
    me = await signup(client)
    h = me["headers"]

    await client.put("/me/keys/openai", json={"value": "sk-test"}, headers=h)
    await client.put("/me/keys/anthropic", json={"value": "ant-y"}, headers=h)

    cid = await _make_conv(client, h)
    mock_runtime["rule"] = lambda r: (200, _build_run(["x"]))

    async with client.stream(
        "POST",
        f"/conversations/{cid}/messages",
        json={"content": "hi"},
        headers=h,
    ) as resp:
        async for _ in resp.aiter_raw():
            pass

    body = json.loads(mock_runtime["requests"][-1]["body"])
    assert body["context"]["credentials"] == {
        "openai_api_key": "sk-test",
        "anthropic_api_key": "ant-y",
    }


async def test_first_message_sets_auto_title(
    client: AsyncClient, session: AsyncSession, mock_runtime: dict
) -> None:
    h = (await signup(client))["headers"]
    cid = await _make_conv(client, h)
    mock_runtime["rule"] = lambda r: (200, _build_run(["ok"]))

    async with client.stream(
        "POST",
        f"/conversations/{cid}/messages",
        json={"content": "What time is it in Paris right now?"},
        headers=h,
    ) as resp:
        async for _ in resp.aiter_raw():
            pass

    conv = await session.get(Conversation, uuid.UUID(cid))
    assert conv is not None
    assert conv.title == "What time is it in Paris right now?"


async def test_auto_title_truncates_long_messages(
    client: AsyncClient, session: AsyncSession, mock_runtime: dict
) -> None:
    h = (await signup(client))["headers"]
    cid = await _make_conv(client, h)
    mock_runtime["rule"] = lambda r: (200, _build_run(["ok"]))

    long_msg = "A very long opening question " * 20
    async with client.stream(
        "POST",
        f"/conversations/{cid}/messages",
        json={"content": long_msg},
        headers=h,
    ) as resp:
        async for _ in resp.aiter_raw():
            pass

    conv = await session.get(Conversation, uuid.UUID(cid))
    assert conv is not None and conv.title is not None
    assert conv.title.endswith("…")
    assert len(conv.title) <= 60


async def test_second_message_keeps_title_and_extends_history(
    client: AsyncClient, session: AsyncSession, mock_runtime: dict
) -> None:
    h = (await signup(client))["headers"]
    cid = await _make_conv(client, h)
    mock_runtime["rule"] = lambda r: (200, _build_run(["first reply"]))

    async with client.stream(
        "POST",
        f"/conversations/{cid}/messages",
        json={"content": "First turn"},
        headers=h,
    ) as resp:
        async for _ in resp.aiter_raw():
            pass

    # Second message: runtime gets THREE messages back (user, assistant, user).
    mock_runtime["rule"] = lambda r: (200, _build_run(["second reply"]))
    async with client.stream(
        "POST",
        f"/conversations/{cid}/messages",
        json={"content": "Second turn"},
        headers=h,
    ) as resp:
        async for _ in resp.aiter_raw():
            pass

    body = json.loads(mock_runtime["requests"][-1]["body"])
    messages = body["input"]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[0]["content"] == "First turn"
    assert messages[1]["content"] == "first reply"
    assert messages[2]["content"] == "Second turn"

    # Title is locked in from the first turn.
    conv = await session.get(Conversation, uuid.UUID(cid))
    assert conv is not None and conv.title == "First turn"


async def test_cancel_proxies_to_runtime(
    client: AsyncClient, mock_runtime: dict
) -> None:
    h = (await signup(client))["headers"]
    cid = await _make_conv(client, h)

    # Simulate an in-flight run by populating the tracker directly. The
    # alternative (driving a real upstream stream that blocks) requires more
    # plumbing for no extra coverage of the cancel proxy itself.
    chat_module._active_runs[uuid.UUID(cid)] = "run-xyz"

    mock_runtime["rule"] = lambda r: httpx.Response(200, json={"cancelled": True})
    r = await client.post(f"/conversations/{cid}/cancel", headers=h)
    assert r.status_code == 200 and r.json() == {"cancelled": True}

    sent = mock_runtime["requests"][-1]
    assert sent["path"] == "/agents/fake-1/cancel"
    assert sent["method"] == "POST"
    # Per CONTRACT.md §2: run_id rides in the body, not the URL.
    assert json.loads(sent["body"]) == {"run_id": "run-xyz"}


async def test_cancel_with_no_active_run_returns_false(
    client: AsyncClient, mock_runtime: dict
) -> None:
    h = (await signup(client))["headers"]
    cid = await _make_conv(client, h)
    r = await client.post(f"/conversations/{cid}/cancel", headers=h)
    assert r.status_code == 200 and r.json() == {"cancelled": False}
    # No upstream call should have been made — there's nothing to cancel.
    assert mock_runtime["requests"] == []


async def test_action_proxy_forwards_args_and_passes_response(
    client: AsyncClient, mock_runtime: dict
) -> None:
    h = (await signup(client))["headers"]
    cid = await _make_conv(client, h)

    mock_runtime["rule"] = lambda r: httpx.Response(200, json={"result": "pong"})

    r = await client.post(
        f"/conversations/{cid}/actions/ping",
        json={"args": {"reps": 3}},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json() == {"result": "pong"}

    sent = mock_runtime["requests"][-1]
    assert sent["path"] == "/agents/fake-1/actions/ping"
    assert json.loads(sent["body"]) == {"args": {"reps": 3}}


async def test_chat_requires_auth(client: AsyncClient, mock_runtime: dict) -> None:
    for path, method in (
        ("/conversations/00000000-0000-0000-0000-000000000000/messages", "post"),
        ("/conversations/00000000-0000-0000-0000-000000000000/cancel", "post"),
        ("/conversations/00000000-0000-0000-0000-000000000000/actions/x", "post"),
    ):
        r = await getattr(client, method)(path, json={"content": "x"})
        assert r.status_code == 401, f"{path} should require auth"


async def test_other_users_conversation_is_404_on_chat(
    client: AsyncClient, mock_runtime: dict
) -> None:
    alice = await signup(client, email="alice@x.io")
    bob = await signup(client, email="bob@x.io")
    cid = await _make_conv(client, alice["headers"])

    r = await client.post(
        f"/conversations/{cid}/messages",
        json={"content": "hi"},
        headers=bob["headers"],
    )
    assert r.status_code == 404
