"""Shared helpers for the deepagents/LangChain agents (itsm, hr).

``astream_events`` yields live LangChain objects (AIMessageChunk, ToolMessage, …)
the agent-server's ``json.dumps`` framing can't serialize, so ``to_native_event``
projects each down to the plain wire shape the proxy's LangChain translator reads;
ignored events (on_chain_*, on_retriever_*, …) are dropped.
"""

from __future__ import annotations

from typing import Any

from .. import protocol


def messages_input(input: Any) -> dict[str, Any]:
    """Coerce the contract input into the ``{"messages": [...]}`` LangGraph wants."""
    messages = (input or {}).get("messages") if isinstance(input, dict) else None
    if isinstance(messages, list) and messages:
        return {"messages": messages}
    return {"messages": [{"role": "user", "content": protocol.last_user_text(input)}]}


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
