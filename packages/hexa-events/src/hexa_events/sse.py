"""
SSE wire serialization for the HexaUI streaming contract.

A backend serves the stream as ``text/event-stream`` and frames each
:class:`~hexa_events.events.StreamEvent` with :func:`to_sse_frame`, which emits
raw bytes in exactly the shape the proxy's parser expects::

    event: <event_type>\n
    id: <event_id>\n
    data: <compact-json>\n
    \n

Frames are ``\\n\\n``-delimited. This matches ``platform_backend.sse.iter_frames``
byte-for-byte, so the proxy can pipe the bytes straight to the browser while
tee-parsing them for persistence.
"""

from __future__ import annotations

import json

from .events import StreamEvent


def to_sse_frame(event: StreamEvent) -> bytes:
    """Serialize one ``StreamEvent`` into a single SSE frame (raw bytes).

    The ``event:`` name is the platform ``event_type``; ``id:`` is the
    ``event_id`` (used by EventSource for ``Last-Event-ID``); ``data:`` is the
    compact JSON payload.
    """
    payload = event.model_dump(mode="json")
    body = json.dumps(payload, separators=(",", ":"))
    frame = (
        f"event: {payload['event_type']}\n"
        f"id: {payload['event_id']}\n"
        f"data: {body}\n\n"
    )
    return frame.encode("utf-8")
