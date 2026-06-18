"""ITSM Change-Request agent — RBAC + state-machine guard (deepagents/LangChain).

Vendored from ``hexgate/examples/itsm_agent.py``; the HexaUI wrapper is ``itsm.py``.
Two checks per action: the policy answers "does the ROLE grant this tool?" (each
transition is its own tool, so separation of duties is structural); the tool body
answers "is the transition valid from the current state, and does the actor own
the record?" — keyed off the trusted ``User`` the policy can't see.

Identity = the caller's NAME (HexUI never forwards email — see ``itsm_db``), so
ownership compares against ``requester_name`` / ``implementer_name``.

    new ──(requester)──▶ Assess ──(change_manager)──▶ Authorize ──(cab_manager)──▶ Schedule
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from . import itsm_db as db

# Load .env at import — the model (and the eager `agent` below, which `hexgate
# register` resolves) needs OPENAI_API_KEY at construction time.
load_dotenv()

# Each transition tool maps to (required from_state, to_state). The role is
# enforced by the policy (one tool per role); the from-state, in the tool body.

_TRANSITIONS = {
    "submit_for_assessment": ("new", "Assess"),
    "authorize_change": ("Assess", "Authorize"),
    "schedule_change": ("Authorize", "Schedule"),
}


def _actor() -> tuple[str, str | None]:
    """Trusted caller identity (name, role) from the active User scope."""
    from hexgate.runtime import get_current_user

    user = get_current_user()
    if user is None:  # no scope → fail closed
        return ("anonymous", None)
    return (user.user_id, user.role)


def _fmt(change: dict) -> str:
    return (
        f"{change['number']} [{change['state']}] CI={change['ci']} "
        f"\"{change['short_description']}\" requester={change['requester_name']} "
        f"implementer={change['implementer_name']}"
    )


def _transition(tool_name: str, change_id: str) -> str:
    """Shared guard for the three transitions: the change must be in the expected
    ``from`` state (role is already enforced by the policy), and — for the
    requester's submit — the actor must own the record."""
    actor_name, role = _actor()
    from_state, to_state = _TRANSITIONS[tool_name]
    change = db.get_change(change_id)
    if change is None:
        db.audit(action=tool_name, actor=actor_name, role=role, number=change_id,
                 decision="DENY", detail="not found")
        return f"DENIED: change {change_id} not found."

    if change["state"] != from_state:
        db.audit(action=tool_name, actor=actor_name, role=role, number=change_id,
                 decision="DENY", before=change["state"], detail=f"requires {from_state}")
        return (
            f"DENIED: {tool_name} requires state '{from_state}', but "
            f"{change_id} is in '{change['state']}'."
        )

    # Only the requester's own draft may be submitted.
    if tool_name == "submit_for_assessment" and change["requester_name"] != actor_name:
        db.audit(action=tool_name, actor=actor_name, role=role, number=change_id,
                 decision="DENY", before=change["state"], detail="not owner")
        return f"DENIED: {change_id} is not your change."

    updated = db.set_state(change_id, to_state)
    db.audit(action=tool_name, actor=actor_name, role=role, number=change_id,
             decision="ALLOW", before=from_state, after=to_state)
    return f"OK: {change_id} transitioned {from_state} → {to_state}.\n{_fmt(updated)}"


# Tools — RBAC (role → tool) is the policy's job; each body enforces the
# state-machine + ownership the policy can't see.


@tool
async def create_change(ci: str, short_description: str) -> str:
    """Create a new change request on a CI (a server or application) by name.

    `ci` is a CMDB CI name such as 'srv-db-01' or 'CRM'. The new change is
    forced to state 'new' and owned by the calling user.
    """
    actor_name, role = _actor()
    try:
        created = db.create_change(
            short_description=short_description, ci_name=ci, requester_name=actor_name
        )
    except ValueError as exc:
        db.audit(action="create_change", actor=actor_name, role=role, number=None,
                 decision="DENY", detail=str(exc))
        return f"DENIED: {exc} (known CIs: srv-web-01/02, srv-db-01, srv-app-01, CRM, ERP, Billing)."
    db.audit(action="create_change", actor=actor_name, role=role,
             number=created["number"], decision="ALLOW", after="new", detail=f"CI={ci}")
    return f"OK: created {created['number']} in state 'new'.\n{_fmt(created)}"


@tool
async def update_change(change_id: str, description: str = "", ci: str = "") -> str:
    """Edit a DRAFT change. Pass `description` and/or `ci` (a CI name) to set.

    Allowed only while the change is in state 'new' and owned by the caller —
    write access expires once the change moves past 'new'.
    """
    actor_name, role = _actor()
    change = db.get_change(change_id)
    if change is None:
        return f"DENIED: change {change_id} not found."

    if change["state"] != "new":
        db.audit(action="update_change", actor=actor_name, role=role, number=change_id,
                 decision="DENY", before=change["state"], detail="not editable past 'new'")
        return f"DENIED: {change_id} is in '{change['state']}'; drafts are editable only while 'new'."
    if change["requester_name"] != actor_name:
        db.audit(action="update_change", actor=actor_name, role=role, number=change_id,
                 decision="DENY", before=change["state"], detail="not owner")
        return f"DENIED: {change_id} is not your draft."

    try:
        updated = db.update_change_fields(
            change_id,
            description=description or None,
            ci_name=ci or None,
        )
    except ValueError as exc:
        db.audit(action="update_change", actor=actor_name, role=role, number=change_id,
                 decision="DENY", detail=str(exc))
        return f"DENIED: {exc}."
    db.audit(action="update_change", actor=actor_name, role=role, number=change_id,
             decision="ALLOW", before="new", after="new")
    return f"OK: updated {change_id}.\n{_fmt(updated)}"


@tool
async def read_change(change_id: str) -> str:
    """Return a single change request by number (e.g. 'CHG0001')."""
    actor_name, role = _actor()
    change = db.get_change(change_id)
    # Implementers may read ONLY changes they are mentioned on. Return
    # 'not found' on a miss so the existence of unrelated changes never leaks.
    if change is None or (
        role == "implementer" and change["implementer_name"] != actor_name
    ):
        db.audit(action="read_change", actor=actor_name, role=role, number=change_id,
                 decision="DENY", detail="not found / out of scope")
        return f"Not found: {change_id}."
    db.audit(action="read_change", actor=actor_name, role=role, number=change_id,
             decision="ALLOW", before=change["state"])
    return _fmt(change)


@tool
async def list_my_changes() -> str:
    """List the change requests visible to the calling user."""
    actor_name, role = _actor()
    changes = db.all_changes()
    # Filter to the caller's scope BEFORE returning — no unrelated rows leak.
    if role == "requester":
        visible = [c for c in changes if c["requester_name"] == actor_name]
    elif role == "implementer":
        visible = [c for c in changes if c["implementer_name"] == actor_name]
    elif role in ("change_manager", "cab_manager"):
        visible = changes
    else:
        visible = []
    db.audit(action="list_my_changes", actor=actor_name, role=role, number=None,
             decision="ALLOW", detail=f"{len(visible)} visible")
    if not visible:
        return "No changes visible to you."
    return "\n".join(_fmt(c) for c in visible)


@tool
async def submit_for_assessment(change_id: str) -> str:
    """Submit your draft change for assessment (transition new → Assess)."""
    return _transition("submit_for_assessment", change_id)


@tool
async def update_assessment(change_id: str, short_description: str) -> str:
    """Update assessment details on a change under review (state must be 'Assess')."""
    actor_name, role = _actor()
    change = db.get_change(change_id)
    if change is None:
        return f"DENIED: change {change_id} not found."
    if change["state"] != "Assess":
        db.audit(action="update_assessment", actor=actor_name, role=role, number=change_id,
                 decision="DENY", before=change["state"], detail="requires Assess")
        return f"DENIED: assessment edits require state 'Assess'; {change_id} is in '{change['state']}'."
    updated = db.update_change_fields(change_id, description=short_description)
    db.audit(action="update_assessment", actor=actor_name, role=role, number=change_id,
             decision="ALLOW", before="Assess", after="Assess")
    return f"OK: updated assessment on {change_id}.\n{_fmt(updated)}"


@tool
async def authorize_change(change_id: str) -> str:
    """Authorize an assessed change (transition Assess → Authorize)."""
    return _transition("authorize_change", change_id)


@tool
async def schedule_change(change_id: str, cab_decision: str) -> str:
    """Record the CAB decision and schedule the change (transition Authorize → Schedule).

    `cab_decision` is the CAB's note (e.g. 'approved for Saturday window').
    Decision-only: no change fields are edited here.
    """
    actor_name, role = _actor()
    from_state, to_state = _TRANSITIONS["schedule_change"]
    change = db.get_change(change_id)
    if change is None:
        return f"DENIED: change {change_id} not found."
    if change["state"] != from_state:
        db.audit(action="schedule_change", actor=actor_name, role=role, number=change_id,
                 decision="DENY", before=change["state"], detail=f"requires {from_state}")
        return f"DENIED: scheduling requires state '{from_state}'; {change_id} is in '{change['state']}'."
    updated = db.set_state(change_id, to_state)
    db.audit(action="schedule_change", actor=actor_name, role=role, number=change_id,
             decision="ALLOW", before=from_state, after=to_state,
             detail=f"CAB: {cab_decision}")
    return f"OK: {change_id} scheduled (Authorize → Schedule). CAB decision: {cab_decision}.\n{_fmt(updated)}"


TOOLS = [
    create_change,
    update_change,
    read_change,
    list_my_changes,
    submit_for_assessment,
    update_assessment,
    authorize_change,
    schedule_change,
]

INSTRUCTIONS = (
    "You are an ITSM assistant operating a Change Request workflow. Help "
    "authorized staff create change requests, edit drafts, read changes, "
    "update assessment details, and move a change through its lifecycle "
    "(new → Assess → Authorize → Schedule). Map the user's request to the "
    "right tool, pulling the change number (CHGxxxx), the CI name "
    "(server or application), and field values straight from their message. "
    "Do not ask the user to confirm before invoking a tool — act directly on "
    "the details given. "
    "ALWAYS use a tool for any change-request action or information lookup: "
    "every create, edit, read, list, assessment update, and lifecycle "
    "transition MUST go through its tool — never answer about a change, or "
    "claim one was modified, from memory or the conversation history. Treat "
    "ONLY the tool results as the source of truth: state, ownership, and field "
    "values come from the latest tool output, not from anything said earlier "
    "in the conversation (a change may have moved or been edited since). If you "
    "need information you don't have a fresh tool result for, call the tool "
    "first. "
    "The policy layer and the workflow guard gate sensitive actions, so trust "
    "them to stop anything you're not allowed to do. Always respond in the same "
    "language as the user's message."
)


# Built at import so `hexgate register` can resolve `…itsm_agent:agent`;
# `stream_as` wraps it with HexGate policy enforcement at call time.
def _build_agent() -> Any:
    from deepagents import create_deep_agent

    built = create_deep_agent(
        model=ChatOpenAI(model="gpt-4o-mini", temperature=0),
        tools=TOOLS,
        system_prompt=INSTRUCTIONS,
    )
    built.name = "itsm_agent"  # policy + manifest resolve by this name on the platform
    return built


agent = _build_agent()

# Enforced wrapper, built once on first gated use — `wrap_langchain_agent`
# mutates TOOLS in place, so re-running it per request would re-wrap them.
# One wrapper serves all users; `user` is passed per call.
_enforced: Any | None = None


def _enforced_agent() -> Any:
    global _enforced
    if _enforced is None:
        from hexgate.adapters.langchain import wrap_langchain_agent

        _enforced = wrap_langchain_agent(agent=agent, tools=TOOLS)
    return _enforced


# Invocation — yield LangChain astream_events items for the proxy.


def _messages_input(input: Any) -> dict[str, Any]:
    """Coerce the contract input into the ``{"messages": [...]}`` LangGraph wants."""
    messages = (input or {}).get("messages") if isinstance(input, dict) else None
    if isinstance(messages, list) and messages:
        return {"messages": messages}
    from .. import protocol

    return {"messages": [{"role": "user", "content": protocol.last_user_text(input)}]}


async def stream(input: Any) -> AsyncIterator[Any]:
    """Stream the plain (ungated) deepagent graph, yielding astream_events items."""
    async for event in agent.astream_events(_messages_input(input), version="v2"):
        yield event


async def stream_as(input: Any, *, user_id: str, role: str) -> AsyncIterator[Any]:
    """Same as :func:`stream`, but policy-gated against the caller. ``user_id`` is
    the caller's NAME (tools read it back via ``get_current_user()`` for ownership
    / scope); ``role`` is the opaque role from ``context.user``."""
    from hexgate.runtime import User

    user = User(user_id=user_id, role=role, session_id="hexui-demo-itsm")
    async for event in _enforced_agent().astream_events(
        _messages_input(input), user=user
    ):
        yield event


# LangChain astream_events → JSON-serializable native event. astream_events
# yields live objects (AIMessageChunk, ToolMessage, …) the agent-server's
# json.dumps framing can't serialize, so project each down to the plain wire
# shape the proxy's translator reads; ignored events (on_chain_*, …) are dropped.


def _text_of(obj: Any) -> str:
    """Pull printable text from a LangChain message/chunk (or dict/str)."""
    content = getattr(obj, "content", None)
    if content is None and isinstance(obj, dict):
        content = obj.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            p["text"]
            for p in content
            if isinstance(p, dict) and isinstance(p.get("text"), str)
        ]
        return "".join(parts)
    return obj if isinstance(obj, str) else ""


def _jsonable(value: Any) -> Any:
    """Best-effort JSON-safe coercion for tool-call arguments."""
    import json

    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {k: _jsonable(v) for k, v in value.items()}
        return str(value)


def to_native_event(event: dict[str, Any]) -> dict | None:
    """Project one LangChain ``astream_events`` item into a JSON-safe native
    event for the proxy's LangChain translator (``None`` to drop it)."""
    name = event.get("event")
    run_id = event.get("run_id", "")
    ev_name = event.get("name")
    data = event.get("data") or {}

    if name in ("on_chat_model_stream", "on_llm_stream"):
        text = _text_of(data.get("chunk"))
        if not text:
            return None
        return {"event": name, "run_id": run_id, "name": ev_name,
                "data": {"chunk": {"content": text}}}

    if name in ("on_chat_model_end", "on_llm_end"):
        return {"event": name, "run_id": run_id, "name": ev_name,
                "data": {"output": {"content": _text_of(data.get("output"))}}}

    if name == "on_tool_start":
        return {"event": name, "run_id": run_id, "name": ev_name,
                "data": {"input": _jsonable(data.get("input"))}}

    if name == "on_tool_end":
        return {"event": name, "run_id": run_id, "name": ev_name,
                "data": {"output": _text_of(data.get("output"))}}

    return None
