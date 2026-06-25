"""In-process per-conversation memory for the reference agents.

The HexUI proxy sends only the **new** user turn (CONTRACT.md §5) — the backend
owns conversation memory. This module is that store for agent-server: a dict
keyed by ``conversation_id`` holding the running transcript. The stream route
(``routes/agents.py``) appends the incoming user turn, hands the agent the full
reconstructed transcript as ``input.messages``, then appends the assistant's
reply once the run finishes.

It is the simplest thing that satisfies the contract — **in-process only**, so a
restart forgets everything. That's fine for a demo; a real backend swaps this
for its own durable store (Redis, a DB, the framework's session service, …)
behind the same three functions. Single asyncio loop, so no locking needed.
"""

from __future__ import annotations

_store: dict[str, list[dict[str, str]]] = {}


def history(conversation_id: str | None) -> list[dict[str, str]]:
    """The full transcript for a conversation (empty for an unknown/cold id)."""
    if not conversation_id:
        return []
    return list(_store.get(conversation_id, []))


def append(conversation_id: str | None, role: str, content: str) -> None:
    """Append one message. No-ops on a missing id or empty content."""
    if not conversation_id or not content:
        return
    _store.setdefault(conversation_id, []).append({"role": role, "content": content})


def forget(conversation_id: str | None) -> bool:
    """Drop a conversation's memory. Returns whether anything was stored."""
    if not conversation_id:
        return False
    return _store.pop(conversation_id, None) is not None
