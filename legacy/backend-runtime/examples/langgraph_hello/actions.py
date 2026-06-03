"""
UI-triggered actions for `langgraph-hello`.

The manifest's `actions:` field lists the names exposed here. The
front-end's dispatcher forwards any action it doesn't handle locally
(e.g. `cancel-run`) to the runtime, which routes to one of these
functions. The return value goes back to `dispatcher.invoke()`; events
emitted via `context.emit(widget, payload)` are fanned out by the
front-end as `tool-call` events targeted at the named widget.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


async def server_ping(args, *, context):
    """Round-trip — proves the action wire is live without side effects."""
    return {
        "pong": True,
        "received_args": args,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


async def inject_tool_log(args, *, context):
    """Push a synthetic entry into the `tool-calls` widget.

    Demonstrates that an action handler can update any inbox-aware widget
    by emitting `tool-call`-shaped payloads. The widget folds these into
    rows just as it does for real tool invocations during a run.
    """
    call_id = uuid4().hex
    note = str(args.get("note") or "manual injection from /actions")

    # An `end` without a preceding `start` is synthesized as a one-shot
    # completed row by the tool-calls widget — that's the lightest demo.
    context.emit(
        widget="tool-calls",
        payload={
            "phase": "end",
            "id": call_id,
            "name": "inject_tool_log",
            "output": {
                "note": note,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
        },
    )
    return {"injected": True, "id": call_id}
