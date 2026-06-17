"""The contract endpoints the HexaUI proxy calls.

    GET  /agents                       roster
    GET  /agents/{id}/ui               per-agent ui.yaml (text/yaml)
    POST /agents/{id}/stream           SSE run
    POST /agents/{id}/cancel           body {run_id} -> {cancelled}
    POST /agents/{id}/forget           body {conversation_id} -> {forgotten}
    POST /agents/{id}/actions/{name}   optional widget action
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from .. import memory, protocol
from ..actions import run_action
from ..agents.select import select_agent
from ..roster import AGENTS, get_agent, read_ui

router = APIRouter(prefix="/agents", tags=["agents"])


def _assistant_text(framework: str, event: dict) -> str:
    """Best-effort assistant-text delta from a native event, so the route can
    record the reply into conversation memory. Mirrors the text shapes each
    translator reads (CONTRACT.md §6); anything else contributes nothing."""
    if not isinstance(event, dict):
        return ""
    if framework == "native":
        return event.get("text", "") if event.get("type") == "text" else ""
    if framework in ("langchain", "langgraph", "deepagents"):
        if event.get("event") == "on_chat_model_stream":
            chunk = (event.get("data") or {}).get("chunk") or {}
            return chunk.get("content", "") if isinstance(chunk.get("content"), str) else ""
        return ""
    if framework == "openai-agents":
        data = event.get("data") or {}
        if event.get("type") == "raw_response" and data.get("type") == "response.output_text.delta":
            return data.get("delta", "") or ""
        return ""
    if framework == "google-adk":
        # Streamed text deltas; skip the turn_complete marker to avoid doubling.
        if event.get("turn_complete"):
            return ""
        parts = (event.get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text"))
    return ""


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
    conversation_id = context.get("conversation_id")

    # The proxy sends only the new turn (CONTRACT.md §5); WE own the memory.
    # Append the incoming user turn, then hand the agent the full reconstructed
    # transcript as `input.messages` (so the agents stay framework-agnostic and
    # unchanged). Idempotency on retries is left out for brevity — see §5 rule 5.
    for m in (input.get("messages") or []):
        if isinstance(m, dict) and m.get("role") == "user":
            memory.append(conversation_id, "user", str(m.get("content", "")))
    full_input = {"messages": memory.history(conversation_id)}

    cancel_event = asyncio.Event()
    runs: dict[str, asyncio.Event] = request.app.state.runs
    runs[run_id] = cancel_event
    agent = select_agent(agent_id, context)

    framework = getattr(agent, "framework", "native")

    async def event_source():
        reply_parts: list[str] = []
        try:
            async for ev in agent.run(input=full_input, context=context):
                # Stop on cancel/disconnect. We just end the stream — the proxy
                # synthesizes run_end and persists whatever it accumulated.
                if cancel_event.is_set() or await request.is_disconnected():
                    return
                reply_parts.append(_assistant_text(framework, ev))
                # Tag each native event with its framework so the proxy picks
                # the right translator.
                yield protocol.to_sse({"framework": framework, "event": ev})
        except Exception as e:  # noqa: BLE001
            yield protocol.to_sse(
                {"framework": "native", "event": protocol.error(f"agent failed: {e}")}
            )
        finally:
            runs.pop(run_id, None)
            # Record the assistant reply so the next turn sees it.
            memory.append(conversation_id, "assistant", "".join(reply_parts).strip())

    return StreamingResponse(event_source(), media_type="text/event-stream")


@router.post("/{agent_id}/cancel")
async def cancel(agent_id: str, body: dict[str, Any], request: Request) -> dict:
    run_id = (body or {}).get("run_id")
    ev = request.app.state.runs.get(run_id) if run_id else None
    if ev is None:
        return {"cancelled": False}
    ev.set()
    return {"cancelled": True}


@router.post("/{agent_id}/forget")
async def forget(agent_id: str, body: dict[str, Any] | None = None) -> dict:
    """Erase a conversation's memory (CONTRACT.md §5). The proxy calls this when
    the user deletes a conversation. Idempotent — an unknown id is still 200."""
    if get_agent(agent_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_id}'")
    conversation_id = (body or {}).get("conversation_id")
    return {"forgotten": memory.forget(conversation_id)}


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
