"""Event schema: serialization round-trip and discriminated union parsing."""

from __future__ import annotations

import json

from pydantic import TypeAdapter

from platform_runtime.events import (
    ApprovalRequestedEvent,
    ApprovalSource,
    BlockDeltaEvent,
    BlockType,
    RunEndEvent,
    StreamEvent,
)


_adapter = TypeAdapter(StreamEvent)


def test_serialize_then_parse_roundtrip() -> None:
    ev = BlockDeltaEvent(
        run_id="r",
        root_run_id="r",
        sequence=3,
        block_id="b",
        block_type=BlockType.TEXT,
        text="hi",
    )
    payload = ev.model_dump(mode="json")
    blob = json.dumps(payload)
    parsed = _adapter.validate_json(blob)
    assert isinstance(parsed, BlockDeltaEvent)
    assert parsed.text == "hi"
    assert parsed.sequence == 3


def test_discriminated_union_picks_run_end() -> None:
    raw = {
        "event_id": "x",
        "run_id": "r",
        "root_run_id": "r",
        "sequence": 1,
        "event_type": "run_end",
        "result": {
            "run_id": "r",
            "root_run_id": "r",
            "message": "done",
            "steps": [],
        },
    }
    parsed = _adapter.validate_python(raw)
    assert isinstance(parsed, RunEndEvent)
    assert parsed.result.message == "done"


def test_discriminated_union_picks_approval_requested() -> None:
    """The new HITL event parses through the shared union by event_type."""
    raw = {
        "event_id": "x",
        "run_id": "r",
        "root_run_id": "r",
        "sequence": 2,
        "event_type": "approval_requested",
        "approval_id": "ap1",
        "source": "policy",
        "kind": "authorize",
        "reason": "deletion requires approval",
        "tool_name": "delete_file",
    }
    parsed = _adapter.validate_python(raw)
    assert isinstance(parsed, ApprovalRequestedEvent)
    assert parsed.source == ApprovalSource.POLICY
    assert parsed.tool_name == "delete_file"
