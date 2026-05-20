"""
Inter-process wire protocol used between the parent (server) and per-agent
worker processes.

Transport: JSON-lines over stdio. One JSON object per line, no embedded
newlines, no framing other than `\n`. The parent writes requests to the
worker's stdin; the worker writes responses to its stdout. Stderr is left
free for logs / diagnostics — never written to by the wire protocol.

Frames
------
Requests (parent → child):

    {"id": "<corr>", "method": "<m>", "params": {...}}

Where method ∈ {"invoke", "stream", "tools", "metadata", "health", "close"}.

Responses (child → parent):

    {"ready": true}                                   (one-shot, sent at startup)
    {"id": "<corr>", "result": <payload>}             (non-streaming methods)
    {"id": "<corr>", "event":  <RuntimeEvent dict>}   (per-event during stream)
    {"id": "<corr>", "end":    true}                  (terminates a stream)
    {"id": "<corr>", "error":  {"message": "...",
                                 "type": "<ExcName>"}} (per-request failure)
    {"fatal": {"message": "..."}}                     (worker cannot continue)

Design notes
------------
- The frame shape is intentionally minimal. We discriminate on the presence
  of keys (`result` vs `event` vs `end` vs `error`) rather than a `kind`
  field. Concise, easy to write by hand, and Pydantic isn't needed for the
  response side at all.
- Request validation IS done with Pydantic on the worker side so a malformed
  frame can be rejected with a clear error.
- Stream frames are correlated by `id`. Multiple streams may interleave on
  the same pipe; the parent demultiplexes by `id`.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, IO, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request envelope (validated on the worker side)
# ---------------------------------------------------------------------------

WorkerMethod = Literal[
    "invoke",
    "stream",
    "tools",
    "metadata",
    "health",
    "cancel",
    "action",
    "close",
]


class WorkerRequest(BaseModel):
    """One RPC frame from parent to worker."""

    id: str
    method: WorkerMethod
    params: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Response frame constructors
# ---------------------------------------------------------------------------

def frame_ready() -> dict[str, Any]:
    return {"ready": True}


def frame_result(corr_id: str, payload: Any) -> dict[str, Any]:
    return {"id": corr_id, "result": payload}


def frame_event(corr_id: str, event_payload: dict[str, Any]) -> dict[str, Any]:
    return {"id": corr_id, "event": event_payload}


def frame_end(corr_id: str) -> dict[str, Any]:
    return {"id": corr_id, "end": True}


def frame_error(corr_id: str, message: str, exc_type: str) -> dict[str, Any]:
    return {"id": corr_id, "error": {"message": message, "type": exc_type}}


def frame_fatal(message: str) -> dict[str, Any]:
    return {"fatal": {"message": message}}


# ---------------------------------------------------------------------------
# Synchronous frame I/O (used by the worker; the parent uses asyncio streams)
# ---------------------------------------------------------------------------

def encode_frame(frame: dict[str, Any]) -> bytes:
    """Serialize a frame to bytes ending in a single newline.

    `separators` removes whitespace so no spurious `\n` sneaks in via
    `json.dumps` default formatting (it doesn't, but be explicit). The
    trailing `\n` is the framing boundary the reader recovers with
    `readline()`.
    """
    return (json.dumps(frame, separators=(",", ":")) + "\n").encode("utf-8")


def write_frame_sync(stream: IO[bytes], frame: dict[str, Any]) -> None:
    """Synchronous write + flush. Used by the worker on its own stdout.

    Flushing matters: stdout connected to a pipe is block-buffered, so
    without an explicit flush the parent may see nothing until the buffer
    fills (~4 KB). Forgetting this is the #1 reason IPC "seems to hang".
    """
    stream.write(encode_frame(frame))
    stream.flush()


# ---------------------------------------------------------------------------
# Asyncio stdin reader (used by the worker)
# ---------------------------------------------------------------------------

async def connect_stdin_reader() -> asyncio.StreamReader:
    """Wrap the current process's stdin in an asyncio StreamReader.

    This is the standard pattern for reading stdin without blocking the
    event loop. `loop.connect_read_pipe` hands stdin's file descriptor to
    the asyncio transport layer; the StreamReaderProtocol then feeds bytes
    into a StreamReader that supports `await reader.readline()`.
    """
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    return reader
