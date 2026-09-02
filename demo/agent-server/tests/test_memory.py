"""Unit tests for the in-process conversation memory (``agent_server.memory``).

The proxy sends only the new turn (CONTRACT §5); this module is the per-conversation
store the stream route appends to and replays. These cover the three functions and
their edge cases (cold ids, empty content, idempotent forget).
"""

from __future__ import annotations

import pytest
from agent_server import memory


@pytest.fixture(autouse=True)
def _clean_store():
    """Each test starts with an empty store (module-level global)."""
    memory._store.clear()
    yield
    memory._store.clear()


def test_history_is_empty_for_cold_id():
    assert memory.history("never-seen") == []


def test_history_none_id_is_empty():
    assert memory.history(None) == []


def test_append_then_history_round_trips_in_order():
    memory.append("c1", "user", "hello")
    memory.append("c1", "assistant", "hi there")
    memory.append("c1", "user", "bye")
    assert memory.history("c1") == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
        {"role": "user", "content": "bye"},
    ]


def test_history_returns_a_copy_not_the_internal_list():
    memory.append("c1", "user", "hello")
    snapshot = memory.history("c1")
    snapshot.append({"role": "user", "content": "mutation"})
    # Mutating the returned list must not leak back into the store.
    assert memory.history("c1") == [{"role": "user", "content": "hello"}]


def test_conversations_are_isolated_by_id():
    memory.append("a", "user", "in a")
    memory.append("b", "user", "in b")
    assert memory.history("a") == [{"role": "user", "content": "in a"}]
    assert memory.history("b") == [{"role": "user", "content": "in b"}]


def test_append_noops_on_missing_id_or_empty_content():
    memory.append(None, "user", "dropped")
    memory.append("c1", "user", "")  # empty content is a no-op
    assert memory.history("c1") == []
    assert memory._store == {}


def test_forget_drops_memory_and_reports_whether_anything_was_stored():
    memory.append("c1", "user", "hello")
    assert memory.forget("c1") is True
    assert memory.history("c1") == []
    # Idempotent: a second forget (or an unknown id) returns False, never raises.
    assert memory.forget("c1") is False
    assert memory.forget("never-seen") is False
    assert memory.forget(None) is False
