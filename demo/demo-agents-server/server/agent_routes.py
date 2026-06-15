from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from typing import Any

from ..agents.agent_listing import AGENTS, _BY_ID, _UI_DIR
from .agent_selector import get_agent_stream


router = APIRouter(prefix="/agents", tags=["agents"])

@router.get("")
async def list_agents() -> list[dict[str, str]]:
    return AGENTS

@router.get("/{agent_id}/ui")
async def get_agent_ui(agent_id: str) -> Response:
    agent = _BY_ID.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    ui_path = _UI_DIR / f"{agent_id}.yml"
    if not ui_path.exists():
        raise HTTPException(status_code=404, detail="UI not found for this agent")
    
    return Response(content=ui_path.read_text(encoding="utf-8"), media_type="text/yaml")

@router.post("/{agent_id}/stream")
async def stream(agent_id: str, body: dict[str, Any], request: Request):
    agent = _BY_ID.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    event_generator = get_agent_stream(agent_id)

    return StreamingResponse(event_generator(request), media_type="text/event-stream")

@router.post("/{agent_id}/cancel")
async def cancel(agent_id: str, body: dict[str, Any], request: Request):
    agent = _BY_ID.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    #TODO cancel the agent's current task based on the body content
    
    return {"cancelled": "True"}

@router.post("/{agent_id}/actions/{actions_name}")
async def invoke_action(agent_id: str, actions_name: str, body: dict[str, Any]):
    agent = _BY_ID.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    #TODO invoke the specified action on the agent based on the body content
    
    return {"invoked": actions_name}