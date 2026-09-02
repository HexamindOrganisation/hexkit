"""
Thin async HTTP client for the developer's agent backend.

One `httpx.AsyncClient` per process, owned by the FastAPI lifespan. Tests
swap the transport via `set_client(...)` so they can drive a `MockTransport`
without standing up a real backend.

The streaming method (`stream`) yields raw upstream bytes so the chat route
can pass them through the wire untouched — the SSE schema is the HexKit
streaming contract, not the proxy's invention.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from .config import get_settings


class RuntimeError_(Exception):  # noqa: N818 — name avoids stdlib clash
    """Raised on non-2xx responses from the backend that the proxy can't pass through."""


_client: httpx.AsyncClient | None = None


def init_client(base_url: str | None = None, transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    global _client
    url = base_url or get_settings().agent_backend_url
    # No follow_redirects: the backend should never redirect us; if it does
    # we want a loud failure rather than silently chasing it through auth
    # checks.
    _client = httpx.AsyncClient(base_url=url, transport=transport, timeout=None)
    return _client


def set_client(client: httpx.AsyncClient) -> None:
    """For tests: install a pre-built AsyncClient (typically with a MockTransport)."""
    global _client
    _client = client


async def dispose_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None


def _client_or_raise() -> httpx.AsyncClient:
    if _client is None:
        # Lazy init lets the chat route work in dev even before the lifespan
        # has run (e.g. a unit test that hits the route directly without
        # the lifespan).
        return init_client()
    return _client


# ---------------------------------------------------------------------------
# Read-only proxy helpers
# ---------------------------------------------------------------------------

async def list_agents() -> list[dict[str, Any]]:
    r = await _client_or_raise().get("/agents")
    r.raise_for_status()
    return r.json()


async def get_ui_yaml(agent_id: str) -> tuple[int, str | None, str]:
    """Return `(status, content_type, body)`. Lets the proxy preserve the
    backend's content-type (text/yaml) and a 404 verbatim."""
    r = await _client_or_raise().get(f"/agents/{agent_id}/ui")
    return r.status_code, r.headers.get("content-type"), r.text


# ---------------------------------------------------------------------------
# Action helpers
# ---------------------------------------------------------------------------

async def cancel(agent_id: str, run_id: str) -> dict[str, Any]:
    r = await _client_or_raise().post(
        f"/agents/{agent_id}/cancel", json={"run_id": run_id}
    )
    r.raise_for_status()
    return r.json()


async def forget(agent_id: str, conversation_id: str) -> dict[str, Any]:
    """Tell the backend to erase a conversation's memory (CONTRACT §5).

    Called when the user deletes a conversation. Best-effort: the agent owns
    the memory, so a failure here must not roll back the proxy-side delete —
    the caller swallows errors.
    """
    r = await _client_or_raise().post(
        f"/agents/{agent_id}/forget", json={"conversation_id": conversation_id}
    )
    r.raise_for_status()
    return r.json()


async def invoke_action(
    agent_id: str, action_name: str, args: dict[str, Any] | None = None
) -> tuple[int, Any]:
    r = await _client_or_raise().post(
        f"/agents/{agent_id}/actions/{action_name}",
        json={"args": args or {}},
    )
    return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------

async def stream(
    agent_id: str, body: dict[str, Any]
) -> AsyncIterator[bytes]:
    """Open the runtime's SSE stream and yield raw chunks.

    httpx's `client.stream("POST", ...)` is a context manager; we expose a
    plain async iterator by leaning on a small wrapper. Callers re-emit
    chunks byte-for-byte to the browser and (in the chat route) tee-parse
    the same bytes to accumulate the assistant message.
    """
    client = _client_or_raise()
    async with client.stream(
        "POST", f"/agents/{agent_id}/stream", json=body
    ) as resp:
        resp.raise_for_status()
        async for chunk in resp.aiter_raw():
            yield chunk
