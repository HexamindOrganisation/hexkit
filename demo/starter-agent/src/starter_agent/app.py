"""The entire HexaUI developer contract, in one file.

This is a **copy-me template**: the smallest backend the HexaUI proxy will talk
to. It implements the five endpoints from CONTRACT.md with a single `native`
echo agent, and nothing else. Read it top to bottom — every endpoint is
annotated with the contract section it satisfies. To build your own agent, copy
this directory, then change the three things marked `# CHANGE ME`.

    GET  /agents                       §3  roster
    GET  /agents/{id}/ui               §4  per-agent ui.yaml (text/yaml)
    POST /agents/{id}/stream           §5  SSE run (framework-tagged events)
    POST /agents/{id}/cancel           §5  body {run_id} -> {cancelled}
    POST /agents/{id}/actions/{name}   §5b widget action / data source (optional)

You forward your framework's **native** events tagged with `framework`; the
proxy synthesizes run_start/run_end, ids, sequence numbers, and block lifecycle.
You never construct any of that. See demo/CONTRACT.md for the full spec and
demo/agent-server/ for a richer reference that exercises every framework.
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

_UI_DIR = Path(__file__).parent / "ui"

# §3 — the GET /agents roster. One entry per agent. `main_color` is the single
# accent color that themes the whole product for this agent; `ui_url` points at
# its ui.yaml; `framework` selects the proxy translator (`native` = the
# zero-translation escape hatch — you emit already-normalized events).
#
# CHANGE ME (1/3): your agent's identity + color.
AGENTS: list[dict[str, str]] = [
    {
        "id": "echo",
        "name": "Echo",
        "role": "Starter agent",
        "main_color": "#6366f1",
        "ui_url": "/agents/echo/ui",
        "framework": "native",
    },
]
_BY_ID = {a["id"]: a for a in AGENTS}


# ── The agent: forward native events ────────────────────────────────────────
# A `native` agent yields the minimal already-normalized events the proxy reads
# directly (the full vocabulary is in CONTRACT.md §6):
#
#   {"type": "text",        "text": "..."}                 assistant text chunk
#   {"type": "reasoning",   "text": "..."}                 thinking chunk (optional)
#   {"type": "tool",        "id", "name", "args", "widget"} a tool call begins
#   {"type": "tool_result", "id", "output" | "error"}      a tool call ends
#   {"type": "error",       "message": "..."}              the run failed
#   {"type": "done"}                                       optional; EOF also ends
#
# CHANGE ME (2/3): replace the echo loop with your model / framework. If you use
# langchain / openai-agents / google-adk instead of `native`, set the agent's
# `framework` accordingly and forward that framework's native events as-is — the
# proxy has a translator for each (CONTRACT.md §6).
async def run_agent(
    *, input: dict[str, Any], context: dict[str, Any], cancel: asyncio.Event
) -> AsyncIterator[dict]:
    query = _last_user_text(input)

    # context.credentials holds the user's decrypted secrets (flat
    # `{provider}_api_key`). Use them only for this run; never persist or log.
    creds = (context or {}).get("credentials") or {}
    has_key = bool(creds.get("openai_api_key"))

    # context.files holds conversation attachments; `content` is decoded text
    # for text mimes, None for binary. Inline them into your prompt as needed.
    files = (context or {}).get("files") or []
    files_note = f" [{len(files)} file(s) attached]" if files else ""

    reply = f"You said: {query}{files_note} (provider key forwarded: {has_key})"

    for word in reply.split(" "):
        if cancel.is_set():
            return  # stop producing; the proxy persists the partial text
        await asyncio.sleep(0.08)  # makes streaming + cancel observable
        yield {"type": "text", "text": word + " "}

    yield {"type": "done"}


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
            async for ev in run_agent(input=input, context=context, cancel=cancel):
                if cancel.is_set() or await request.is_disconnected():
                    return
                # Each frame: data: {"framework": "...", "event": <native event>}
                frame = {"framework": framework, "event": ev}
                yield f"data: {json.dumps(frame, separators=(',', ':'))}\n\n".encode()
        except Exception as e:  # surface failures as a native error event
            err = {"framework": "native", "event": {"type": "error", "message": str(e)}}
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
    """Widget action / data source. Returns a single `{result}` — never pushes to
    the UI. Only needed if your ui.yaml wires `action` / `data_source` widgets;
    the starter ui.yaml is chat-only, so this just echoes. See CONTRACT.md §5b
    and demo/agent-server/actions.py for a real data-source example.

    CHANGE ME (3/3): dispatch `action_name` to your handlers and return data."""
    if agent_id not in _BY_ID:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_id}'")
    args = (body or {}).get("args", {})
    return {"result": {"action": action_name, "args": args}}


def _last_user_text(input: dict[str, Any]) -> str:
    """Best-effort last user message from the `{"messages": [...]}` input."""
    messages = (input or {}).get("messages")
    if isinstance(messages, list):
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                return str(msg.get("content", ""))
    return ""


def create_app() -> FastAPI:
    app = FastAPI(title="HexaUI Starter Agent", version="0.1.0")
    # run_id -> cancel Event. Process-local; a multi-worker deploy needs a
    # shared store. Created here so it exists before any lifespan runs.
    app.state.runs = {}
    app.include_router(router)

    @app.get("/")
    async def root() -> dict:
        return {"service": "starter-agent", "agents": "/agents"}

    return app
