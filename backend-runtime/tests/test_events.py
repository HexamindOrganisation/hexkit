"""Event schema: serialization round-trip and discriminated union parsing."""

from __future__ import annotations

import json

from pydantic import TypeAdapter

from platform_runtime.events import (
    MessageDelta,
    RunCompleted,
    RuntimeEvent,
)


_adapter = TypeAdapter(RuntimeEvent)


def test_serialize_then_parse_roundtrip() -> None:
    ev = MessageDelta(run_id="r", seq=3, message_id="m", delta="hi")
    payload = ev.model_dump(mode="json")
    blob = json.dumps(payload)
    parsed = _adapter.validate_json(blob)
    assert isinstance(parsed, MessageDelta)
    assert parsed.delta == "hi"
    assert parsed.seq == 3


def test_discriminated_union_picks_right_subclass() -> None:
    raw = {
        "id": "x",
        "run_id": "r",
        "ts": "2026-01-01T00:00:00Z",
        "seq": 0,
        "type": "run.completed",
        "agent_id": "a",
        "output": {"ok": True},
    }
    parsed = _adapter.validate_python(raw)
    assert isinstance(parsed, RunCompleted)
    assert parsed.output == {"ok": True}
