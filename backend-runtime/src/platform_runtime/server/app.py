"""
FastAPI application factory.

Exposes the unified runtime over HTTP:

    GET  /agents                    -> list of AgentMetadata
    GET  /agents/{id}/metadata      -> AgentMetadata
    GET  /agents/{id}/tools         -> list[ToolDescriptor]
    GET  /agents/{id}/health        -> HealthStatus
    POST /agents/{id}/invoke        -> RunCompleted (drains the stream)
    POST /agents/{id}/stream        -> text/event-stream of RuntimeEvent

The application is built around a single `AgentRegistry` instance attached to
`app.state`. Tests construct a registry, populate it, and pass it to
`create_app(registry)` directly — no env vars, no global state.

The production entrypoint (`__main__.py`) reads `PLATFORM_AGENTS_DIR` from
the environment, builds a registry via `discover()`, and hands it to
`create_app`.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ..events import RuntimeEvent
from ..protocol import InvokeRequest
from ..registry import AgentRegistry, RegistryError


logger = logging.getLogger("platform_runtime.server")


def create_app(registry: AgentRegistry) -> FastAPI:
    """Build a FastAPI app bound to the given registry."""

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            await registry.aclose()

    app = FastAPI(
        title="Platform Runtime",
        description="Unified runtime for heterogeneous AI agent frameworks",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.registry = registry

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @app.get("/agents")
    async def list_agents() -> list[dict]:
        out = []
        for loaded in registry.list():
            md = await loaded.runtime.metadata()
            out.append(md.model_dump(mode="json"))
        return out

    @app.get("/agents/{agent_id}/metadata")
    async def get_metadata(agent_id: str) -> dict:
        runtime = _resolve(registry, agent_id)
        md = await runtime.metadata()
        return md.model_dump(mode="json")

    @app.get("/agents/{agent_id}/tools")
    async def get_tools(agent_id: str) -> list[dict]:
        runtime = _resolve(registry, agent_id)
        tools = await runtime.tools()
        return [t.model_dump(mode="json") for t in tools]

    @app.get("/agents/{agent_id}/health")
    async def get_health(agent_id: str) -> dict:
        runtime = _resolve(registry, agent_id)
        h = await runtime.health()
        status = 200 if h.ok else 503
        return JSONResponse(h.model_dump(mode="json"), status_code=status)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    @app.post("/agents/{agent_id}/invoke")
    async def invoke(agent_id: str, body: InvokeRequest) -> dict:
        runtime = _resolve(registry, agent_id)
        result = await runtime.invoke(body)
        return result.model_dump(mode="json")

    @app.post("/agents/{agent_id}/stream")
    async def stream(agent_id: str, body: InvokeRequest, request: Request):
        runtime = _resolve(registry, agent_id)

        async def event_source() -> AsyncIterator[dict]:
            # Each yielded dict becomes one SSE frame. sse_starlette handles
            # the wire formatting (event: ..., id: ..., data: ..., \n\n).
            try:
                async for event in runtime.stream(body):
                    if await request.is_disconnected():
                        # Client gave up — stop pulling from the adapter.
                        break
                    yield _to_sse_frame(event)
            except Exception as e:  # noqa: BLE001
                # The adapter is supposed to translate failures to
                # ErrorEvent. If something escapes anyway, surface it as
                # an out-of-band SSE error frame and end the stream.
                logger.exception("Stream collapsed for agent %s", agent_id)
                yield {
                    "event": "error",
                    "data": json.dumps(
                        {"message": f"Stream collapsed: {e}"}
                    ),
                }

        return EventSourceResponse(event_source())

    # ------------------------------------------------------------------
    # Error mapping
    # ------------------------------------------------------------------

    @app.exception_handler(RegistryError)
    async def _registry_error(_: Request, exc: RegistryError):
        # Unknown agent id is the typical case; treat as 404. Other registry
        # errors (duplicate id, etc.) also map cleanly to 404 from the
        # client's perspective: "no such usable agent".
        return JSONResponse({"detail": str(exc)}, status_code=404)

    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve(registry: AgentRegistry, agent_id: str):
    try:
        return registry.get(agent_id).runtime
    except RegistryError as e:
        # Convert to HTTPException so FastAPI returns a clean 404 BEFORE
        # the body parser tries to validate (matters for POST routes).
        raise HTTPException(status_code=404, detail=str(e)) from e


def _to_sse_frame(event: RuntimeEvent) -> dict:
    """Translate a `RuntimeEvent` into a sse-starlette frame dict.

    - `event` — the SSE event name (the platform event type)
    - `id`    — the event id, used by EventSource for `Last-Event-ID`
    - `data`  — JSON-encoded payload
    """
    payload = event.model_dump(mode="json")
    return {
        "event": payload["type"],
        "id": payload["id"],
        "data": json.dumps(payload, separators=(",", ":")),
    }
