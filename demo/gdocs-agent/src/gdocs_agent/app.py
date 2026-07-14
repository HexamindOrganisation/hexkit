"""The five HexKit contract endpoints for the hexgate-gated gdocs agent.

Structurally the same as demo/hexgate-agent/ — five endpoints, SSE framing,
``framework: "hexgate"`` so the proxy selects ``HexgateTranslator`` — with one
addition: a **lifespan** that connects the fake Google Docs MCP server once at
startup and keeps the stdio connection open for the whole process, so the
agent's ``mcp-gdocs-*`` tools can execute across many runs. See CONTRACT.md.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from .agent import run_gdocs_agent, set_mcp_tools, set_openai_key

_UI_DIR = Path(__file__).parent / "ui"
_MCP_SERVER = Path(__file__).parent / "gdocs_mcp_server.py"

# §3 — the GET /agents roster. `framework: "hexgate"` points the proxy at
# HexgateTranslator; the id `docs` is what HexKit shows in the picker.
AGENTS: list[dict[str, str]] = [
    {
        "id": "docs",
        "name": "Docs Assistant",
        "role": "Google-Docs agent (policy-gated)",
        "main_color": "#2563eb",
        "ui_url": "/agents/docs/ui",
        "framework": "hexgate",
    },
]
_BY_ID = {a["id"]: a for a in AGENTS}


router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")  # §3
async def list_agents() -> list[dict[str, str]]:
    return AGENTS


@router.get("/{agent_id}/ui")  # §4
async def get_ui(agent_id: str) -> Response:
    if agent_id not in _BY_ID:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_id}'")
    path = _UI_DIR / f"{agent_id}.yaml"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="No ui.yaml for this agent")
    return Response(content=path.read_text(encoding="utf-8"), media_type="text/yaml")


@router.post("/{agent_id}/stream")  # §5
async def stream(agent_id: str, body: dict[str, Any], request: Request):
    if agent_id not in _BY_ID:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_id}'")

    run_id = body.get("run_id") or uuid.uuid4().hex
    input = body.get("input") or {}
    context = body.get("context") or {}
    framework = _BY_ID[agent_id]["framework"]

    cancel = asyncio.Event()
    request.app.state.runs[run_id] = cancel

    async def event_source() -> AsyncIterator[bytes]:
        try:
            async for ev in run_gdocs_agent(input=input, context=context, cancel=cancel):
                if cancel.is_set() or await request.is_disconnected():
                    return
                frame = {"framework": framework, "event": ev}
                yield f"data: {json.dumps(frame, separators=(',', ':'))}\n\n".encode()
        except Exception as e:  # surface failures as a hexgate error event
            err = {
                "framework": framework,
                "event": {"event_type": "error", "message": str(e)},
            }
            yield f"data: {json.dumps(err)}\n\n".encode()
        finally:
            request.app.state.runs.pop(run_id, None)

    return StreamingResponse(event_source(), media_type="text/event-stream")


@router.post("/{agent_id}/cancel")  # §5
async def cancel(agent_id: str, body: dict[str, Any], request: Request) -> dict:
    run_id = (body or {}).get("run_id")
    ev = request.app.state.runs.get(run_id) if run_id else None
    if ev is None:
        return {"cancelled": False}
    ev.set()
    return {"cancelled": True}


@router.post("/{agent_id}/actions/{action_name}")  # §5b (optional)
async def invoke_action(
    agent_id: str, action_name: str, body: dict[str, Any] | None = None
) -> dict:
    """This agent's ui.yaml is chat-only, so there are no real actions — echo
    for parity with the contract (see CONTRACT.md §5b)."""
    if agent_id not in _BY_ID:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_id}'")
    args = (body or {}).get("args", {})
    return {"result": {"action": action_name, "args": args}}


def _adopt_platform_key() -> None:
    """Make this process able to bind the platform policy for docs_agent.

    The demo boot writes the minted key to a file; adopt it into
    ``HEXGATE_API_KEY`` (without clobbering an explicit env key) and default the
    API URL to the local platform. Harmless no-op outside the one-box demo.
    """
    if not os.getenv("HEXGATE_API_KEY"):
        key_file = Path(os.getenv("HEXGATE_SERVE_KEY_FILE", "/tmp/hexgate_serve_key"))
        if key_file.exists() and (key := key_file.read_text().strip()):
            os.environ["HEXGATE_API_KEY"] = key
    os.environ.setdefault("HEXGATE_API_URL", "http://127.0.0.1:8000")
    # Opt in to platform binding for auto-bind paths; bind_policy=True already
    # forces it, but setting this keeps behavior explicit.
    os.environ.setdefault("HEXGATE_BIND_AGENTS", "1")


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Connect the fake Google Docs MCP server once; keep it open process-wide.

    The toolset's stdio connection must stay open for the agent's tools to
    execute, so we enter it here and hold it for the app's lifetime.
    """
    _adopt_platform_key()
    from hexgate.mcp import MCPServerConfig, MCPToolset

    cfg = MCPServerConfig(
        name="gdocs",
        transport="stdio",
        command=sys.executable,
        args=(str(_MCP_SERVER),),
    )
    async with MCPToolset(cfg) as mcp:
        set_mcp_tools(mcp.tools)
        yield


def create_app() -> FastAPI:
    app = FastAPI(title="HexKit gdocs agent", version="0.1.0", lifespan=_lifespan)
    app.state.runs = {}
    app.include_router(router)

    @app.get("/")
    async def root() -> dict:
        return {"service": "gdocs-agent", "agents": "/agents"}

    # BYOK key handoff — NOT part of the HexKit contract. The demo notebook posts
    # the visitor's OpenAI key here (same container) so this backend can run the
    # model. Held in process memory only; never persisted or logged.
    @app.post("/byok")
    async def byok(body: dict[str, Any]) -> dict:
        set_openai_key((body or {}).get("openai_key"))
        return {"ok": True}

    return app
