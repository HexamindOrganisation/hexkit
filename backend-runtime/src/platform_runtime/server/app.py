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
from fastapi.responses import JSONResponse, PlainTextResponse
from sse_starlette.sse import EventSourceResponse

from ..actions import ActionError
from ..events import RuntimeEvent
from ..protocol import InvokeRequest
from ..registry import AgentRegistry, RegistryError


logger = logging.getLogger("platform_runtime.server")


def create_app(registry: AgentRegistry) -> FastAPI:
    """Build a FastAPI app bound to the given registry."""

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Warm-start any subprocess workers. No-op for in-process mode.
        # A failure here aborts startup before uvicorn binds the port —
        # exactly what we want: a broken worker means the server stays down.
        await registry.start_all()
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

    @app.get("/agents/{agent_id}/ui", response_class=PlainTextResponse)
    async def get_ui(agent_id: str):
        """Return the agent's `ui.yaml` file (as raw YAML text) if present.

        Agents ship their UI definition next to `agent.yaml` — convention,
        not validation: the platform never parses the YAML server-side.
        The front-app hands it to `agent-ui` which validates and renders
        it client-side.

        Returns 404 when the file is absent; clients fall back to a
        default chat layout.
        """
        loaded = registry.get(agent_id)
        ui_path = loaded.root / "ui.yaml"
        if not ui_path.is_file():
            raise HTTPException(
                status_code=404, detail="No ui.yaml for this agent"
            )
        # Read once per request. Small files (kB), no caching needed yet —
        # if this becomes hot, ETag/If-None-Match is the right fix.
        return PlainTextResponse(
            ui_path.read_text(encoding="utf-8"),
            media_type="text/yaml",
        )

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

    @app.post("/agents/{agent_id}/actions/{action_name}")
    async def invoke_action(
        agent_id: str, action_name: str, body: dict | None = None
    ) -> dict:
        """Run a UI-triggered action declared in the agent's manifest.

        Request body is `{ "args": { ... } }` (or absent — args default
        to an empty dict). The response envelope is
        `{ "result": <handler return value>, "events": [...] }`. The
        front-end re-emits `events` through the bridge as `tool-call`
        AgentEvents so the matching widget inbox receives the payload.
        """
        loaded = _resolve_loaded(registry, agent_id)
        if loaded.actions is None:
            raise HTTPException(
                status_code=404,
                detail=f"Agent '{agent_id}' declares no actions",
            )
        args = (body or {}).get("args", {})
        if not isinstance(args, dict):
            raise HTTPException(
                status_code=400, detail="`args` must be a JSON object"
            )
        try:
            result = await loaded.actions.invoke(action_name, args)
        except ActionError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return result.model_dump(mode="json")

    @app.post("/agents/{agent_id}/runs/{run_id}/cancel")
    async def cancel(agent_id: str, run_id: str) -> dict:
        """Request cancellation of an in-flight run.

        Returns `{"cancelled": true}` if the run was found and signaled;
        `{"cancelled": false}` otherwise (already finished, never started,
        or this adapter doesn't support cancellation). Idempotent — calling
        twice on the same run returns `false` on the second call.
        """
        runtime = _resolve(registry, agent_id)
        ok = await runtime.cancel(run_id)
        return {"cancelled": ok}

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


def _resolve_loaded(registry: AgentRegistry, agent_id: str):
    """Like `_resolve` but returns the full `LoadedAgent` (for action access)."""
    try:
        return registry.get(agent_id)
    except RegistryError as e:
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
