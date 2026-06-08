"""The five HexaUI contract endpoints for a fortify-wrapped agent.

Structurally identical to demo/starter-agent/ — same five endpoints, same SSE
framing — with two differences:

  1. the agent's ``framework`` is ``"fortify"`` (not ``"native"``), so the proxy
     selects the ``FortifyTranslator``; and
  2. ``run_fortify_agent`` yields fortify's *own* normalized events, forwarded
     verbatim. We never reshape them — that's the compatibility being tested.

See CONTRACT.md for the spec; each endpoint is annotated with its section.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from .agent import run_fortify_agent

_UI_DIR = Path(__file__).parent / "ui"

# §3 — the GET /agents roster. `framework: "fortify"` is the only line that
# differs from a `native` backend: it points the proxy at FortifyTranslator.
AGENTS: list[dict[str, str]] = [
    {
        "id": "guard",
        "name": "Fortify Guard",
        "role": "Fortify-wrapped agent",
        "main_color": "#10b981",
        "ui_url": "/agents/guard/ui",
        "framework": "fortify",
    },
]
_BY_ID = {a["id"]: a for a in AGENTS}


# ── The five contract endpoints ─────────────────────────────────────────────
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

    run_id = body.get("run_id") or uuid.uuid4().hex  # opaque id, assigned by proxy
    input = body.get("input") or {}
    context = body.get("context") or {}
    framework = _BY_ID[agent_id]["framework"]

    # Register a cancel flag the /cancel route can flip mid-stream.
    cancel = asyncio.Event()
    request.app.state.runs[run_id] = cancel

    async def event_source() -> AsyncIterator[bytes]:
        try:
            async for ev in run_fortify_agent(
                input=input, context=context, cancel=cancel
            ):
                if cancel.is_set() or await request.is_disconnected():
                    return
                # Each frame: data: {"framework": "fortify", "event": <fortify event>}
                frame = {"framework": framework, "event": ev}
                yield f"data: {json.dumps(frame, separators=(',', ':'))}\n\n".encode()
        except Exception as e:  # surface failures as a fortify error event
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
        return {"cancelled": False}  # already finished / unknown run
    ev.set()
    return {"cancelled": True}


@router.post("/{agent_id}/actions/{action_name}")  # §5b (optional)
async def invoke_action(
    agent_id: str, action_name: str, body: dict[str, Any] | None = None
) -> dict:
    """Widget action / data source. This agent's ui.yaml is chat-only, so there
    are no real actions — echo for parity with the contract. See CONTRACT.md §5b
    and demo/agent-server/actions.py for a real data-source example."""
    if agent_id not in _BY_ID:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_id}'")
    args = (body or {}).get("args", {})
    return {"result": {"action": action_name, "args": args}}


def create_app() -> FastAPI:
    app = FastAPI(title="HexaUI Fortify Agent", version="0.1.0")
    # run_id -> cancel Event. Process-local; a multi-worker deploy needs a
    # shared store. Created here so it exists before any lifespan runs.
    app.state.runs = {}
    app.include_router(router)

    @app.get("/")
    async def root() -> dict:
        return {"service": "hexa-gate-agent", "agents": "/agents"}

    return app
