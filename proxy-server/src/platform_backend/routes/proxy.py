"""Read-only proxy of the agent backend's roster + per-agent UI, plus the
agent-scoped widget action passthrough.

The GETs pass bodies through and preserve status codes so a 404 from the backend
stays a 404 to the browser. `/ui` keeps the backend's `text/yaml` content-type so
the FE can render the raw YAML.

`POST /agents/{id}/actions/{name}` is the **conversation-free** action path: a
`data_source` widget (e.g. the DevOps service-state dashboard) reads agent-scoped
state and must work on the greeting, before any conversation exists. The
conversation-scoped variant (`/conversations/{id}/actions/{name}`) is used once a
chat is underway; both forward to the same backend endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response

from .. import runtime_client
from ..access import can_access
from ..auth.deps import current_user
from ..models.user import User
from ..schemas.chat import ActionIn

router = APIRouter(prefix="/agents", tags=["proxy"])


def _require_access(user: User, agent_id: str) -> None:
    if not can_access(user, agent_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No access to agent '{agent_id}'",
        )


@router.get("")
async def list_agents(user: User = Depends(current_user)) -> list:
    """The roster, filtered to the agents this user may reach (see access.py).
    Drives the picker, so the FE only ever shows allowed agents."""
    roster = await runtime_client.list_agents()
    return [a for a in roster if can_access(user, a.get("id", ""))]


@router.get("/{agent_id}/ui")
async def get_ui(agent_id: str, user: User = Depends(current_user)) -> Response:
    _require_access(user, agent_id)
    status_code, content_type, body = await runtime_client.get_ui_yaml(agent_id)
    return Response(
        content=body,
        status_code=status_code,
        media_type=content_type or "text/yaml",
    )


@router.post("/{agent_id}/actions/{action_name}")
async def invoke_action(
    agent_id: str,
    action_name: str,
    body: ActionIn | None = None,
    user: User = Depends(current_user),
) -> JSONResponse:
    """Conversation-free widget action — backs `data_source` widgets on the
    greeting (no conversation yet). Forwards to the backend's
    `/agents/{id}/actions/{name}`, preserving its status + body."""
    _require_access(user, agent_id)
    status_code, payload = await runtime_client.invoke_action(
        agent_id, action_name, (body.args if body else None) or {}
    )
    return JSONResponse(payload, status_code=status_code)
