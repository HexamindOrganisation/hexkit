"""The contract endpoints the HexKit proxy calls.

    GET  /agents                       roster
    GET  /agents/{id}/ui               per-agent ui.yaml (text/yaml)
    POST /agents/{id}/stream           SSE run
    POST /agents/{id}/cancel           body {run_id} -> {cancelled}
    POST /agents/{id}/actions/{name}   optional widget action
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from .. import protocol
from ..actions import run_action
from ..roster import AGENTS, get_agent, read_ui
from ..select import select_agent

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def list_agents() -> list[dict[str, str]]:
    return AGENTS


@router.get("/{agent_id}/ui")
async def get_ui(agent_id: str) -> Response:
    if get_agent(agent_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_id}'")
    text = read_ui(agent_id)
    if text is None:
        raise HTTPException(status_code=404, detail="No ui.yaml for this agent")
    return Response(content=text, media_type="text/yaml")


@router.post("/{agent_id}/stream")
async def stream(agent_id: str, body: dict[str, Any], request: Request):
    if get_agent(agent_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_id}'")

    run_id = body.get("run_id") or uuid.uuid4().hex
    input = body.get("input") or {}
    context = body.get("context") or {}

    cancel_event = asyncio.Event()
    runs: dict[str, asyncio.Event] = request.app.state.runs
    runs[run_id] = cancel_event
    agent = select_agent(agent_id, context)

    framework = getattr(agent, "framework", "native")

    async def event_source():
        try:
            async for ev in agent.run(input=input, context=context):
                # Stop on cancel/disconnect. We just end the stream — the proxy
                # synthesizes run_end and persists whatever it accumulated.
                if cancel_event.is_set() or await request.is_disconnected():
                    return
                # Tag each native event with its framework so the proxy picks
                # the right translator.
                yield protocol.to_sse({"framework": framework, "event": ev})
        except Exception as e:  # noqa: BLE001
            yield protocol.to_sse(
                {"framework": "native", "event": protocol.error(f"agent failed: {e}")}
            )
        finally:
            runs.pop(run_id, None)

    return StreamingResponse(event_source(), media_type="text/event-stream")


@router.post("/{agent_id}/cancel")
async def cancel(agent_id: str, body: dict[str, Any], request: Request) -> dict:
    run_id = (body or {}).get("run_id")
    ev = request.app.state.runs.get(run_id) if run_id else None
    if ev is None:
        return {"cancelled": False}
    ev.set()
    return {"cancelled": True}


@router.post("/{agent_id}/actions/{action_name}")
async def invoke_action(
    agent_id: str, action_name: str, body: dict[str, Any] | None = None
) -> dict:
    """Widget action / data source. An action returns a single `{result}`; it
    never pushes to the UI. Display widgets read their `data_source` via this
    same endpoint, and `refresh` (declared in the ui.yaml) re-pulls them after
    an action — see CONTRACT.md §5b. Known actions (the Orbit workspace) run from
    `actions.py`; any other name echoes so the envelope shape is demonstrable."""
    if get_agent(agent_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_id}'")
    args = (body or {}).get("args", {})
    result = run_action(action_name, args)
    if result is None:
        result = {"action": action_name, "args": args}
    return {"result": result}
