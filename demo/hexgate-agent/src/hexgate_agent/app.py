"""The five HexaUI contract endpoints for a hexgate-wrapped agent.

Structurally identical to demo/starter-agent/ — same five endpoints, same SSE
framing — with two differences:

  1. the agent's ``framework`` is ``"hexgate"`` (not ``"native"``), so the proxy
     selects the ``HexgateTranslator``; and
  2. ``run_hexgate_agent`` yields hexgate's *own* normalized events, forwarded
     verbatim. We never reshape them — that's the compatibility being tested.

See CONTRACT.md for the spec; each endpoint is annotated with its section.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from .agent import run_hexgate_agent

_UI_DIR = Path(__file__).parent / "ui"

# §3 — the GET /agents roster. `framework: "hexgate"` is the only line that
# differs from a `native` backend: it points the proxy at HexgateTranslator.
AGENTS: list[dict[str, str]] = [
    {
        "id": "guard",
        "name": "Hexgate Guard",
        "role": "Hexgate-wrapped agent",
        "main_color": "#10b981",
        "ui_url": "/agents/guard/ui",
        "framework": "hexgate",
    },
]
_BY_ID = {a["id"]: a for a in AGENTS}

# Conversation memory (CONTRACT.md §5): the proxy sends only the new turn, so we
# own the transcript, keyed by conversation_id. In-process; swap for a durable
# store in production.
_MEMORY: dict[str, list[dict[str, str]]] = {}


# ── The contract endpoints ──────────────────────────────────────────────────
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
    conversation_id = context.get("conversation_id")

    # We own memory: the proxy sent only the new turn. Append it, then run the
    # agent against the full transcript for this conversation.
    if conversation_id:
        for m in input.get("messages") or []:
            if isinstance(m, dict) and m.get("role") == "user":
                _MEMORY.setdefault(conversation_id, []).append(
                    {"role": "user", "content": str(m.get("content", ""))}
                )
    history = {"messages": list(_MEMORY.get(conversation_id, []))}

    # Register a cancel flag the /cancel route can flip mid-stream.
    cancel = asyncio.Event()
    request.app.state.runs[run_id] = cancel

    async def event_source() -> AsyncIterator[bytes]:
        reply_parts: list[str] = []
        try:
            async for ev in run_hexgate_agent(
                input=history, context=context, cancel=cancel
            ):
                if cancel.is_set() or await request.is_disconnected():
                    return
                # hexgate streams assistant text as block_delta events.
                if ev.get("event_type") == "block_delta" and ev.get("text"):
                    reply_parts.append(ev["text"])
                # Each frame: data: {"framework": "hexgate", "event": <hexgate event>}
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
            reply = "".join(reply_parts).strip()
            if conversation_id and reply:
                _MEMORY.setdefault(conversation_id, []).append(
                    {"role": "assistant", "content": reply}
                )

    return StreamingResponse(event_source(), media_type="text/event-stream")


@router.post("/{agent_id}/cancel")  # §5
async def cancel(agent_id: str, body: dict[str, Any], request: Request) -> dict:
    run_id = (body or {}).get("run_id")
    ev = request.app.state.runs.get(run_id) if run_id else None
    if ev is None:
        return {"cancelled": False}  # already finished / unknown run
    ev.set()
    return {"cancelled": True}


@router.post("/{agent_id}/forget")  # §5
async def forget(agent_id: str, body: dict[str, Any] | None = None) -> dict:
    """Erase a conversation's memory (the proxy calls this on conversation
    delete). Idempotent — an unknown id is still 200."""
    if agent_id not in _BY_ID:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_id}'")
    conversation_id = (body or {}).get("conversation_id")
    forgotten = _MEMORY.pop(conversation_id, None) is not None if conversation_id else False
    return {"forgotten": forgotten}


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
    app = FastAPI(title="HexaUI Hexgate Agent", version="0.1.0")
    # run_id -> cancel Event. Process-local; a multi-worker deploy needs a
    # shared store. Created here so it exists before any lifespan runs.
    app.state.runs = {}
    app.include_router(router)

    @app.get("/")
    async def root() -> dict:
        return {"service": "hexgate-agent", "agents": "/agents"}

    return app
