"""SSE frame parsing helpers used by the chat route.

The platform backend pipes the runtime's SSE stream through to the browser
byte-for-byte AND tee-parses each frame so it can persist the assistant's
final text in the database. Two consumers of the same upstream bytes.

Frame shape (per the runtime's sse-starlette output):

    event: <event_type>\n
    id: <event_id>\n
    data: <json blob>\n
    \n

Frames are `\n\n`-delimited. A blank-line terminator marks the end of a frame.
We tolerate `\r\n` too — the spec allows it and clients in the wild emit it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class SSEFrame:
    event: str | None
    data_raw: str
    raw_bytes: bytes  # the original wire form including the trailing blank line

    @property
    def data_json(self) -> dict | None:
        """Best-effort JSON decode of the `data:` field. Returns `None` if the
        body isn't JSON — defensive against keepalive comments or non-JSON
        events we don't care about."""
        try:
            return json.loads(self.data_raw)
        except (json.JSONDecodeError, ValueError):
            return None


def _parse_frame(block: bytes) -> SSEFrame | None:
    """Parse one `\\n\\n`-delimited block into an `SSEFrame`.

    A comment-only block (`: keepalive`) returns `None` — we still want to
    pass the bytes through to the client (preserves keepalive), but there's
    nothing for the accumulator to do with it.
    """
    text = block.decode("utf-8", errors="replace")
    event = None
    data_parts: list[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if not line:
            continue
        if line.startswith(":"):  # SSE comment / keepalive
            continue
        if line.startswith("event:"):
            event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            # Multi-line data is concatenated with literal newlines per SSE
            # spec; the runtime doesn't emit multi-line data, but stay robust.
            data_parts.append(line[len("data:"):].lstrip())
    if event is None and not data_parts:
        return None
    return SSEFrame(
        event=event, data_raw="\n".join(data_parts), raw_bytes=block + b"\n\n"
    )


async def iter_frames(
    chunks: AsyncIterator[bytes],
) -> AsyncIterator[SSEFrame]:
    """Buffer raw bytes from `chunks` and yield one `SSEFrame` per
    `\\n\\n`-delimited block. The yielded `raw_bytes` includes the trailing
    blank line so the caller can pipe it straight to the wire."""
    buf = bytearray()
    async for chunk in chunks:
        buf.extend(chunk)
        while True:
            # Find the soonest blank-line terminator, tolerating \r\n\r\n.
            idx_lf = buf.find(b"\n\n")
            idx_crlf = buf.find(b"\r\n\r\n")
            if idx_lf == -1 and idx_crlf == -1:
                break
            if idx_lf == -1:
                idx, sep_len = idx_crlf, 4
            elif idx_crlf == -1:
                idx, sep_len = idx_lf, 2
            else:
                # Pick whichever ends first.
                if idx_crlf < idx_lf:
                    idx, sep_len = idx_crlf, 4
                else:
                    idx, sep_len = idx_lf, 2

            block = bytes(buf[:idx])
            terminator = bytes(buf[idx : idx + sep_len])
            del buf[: idx + sep_len]

            frame = _parse_frame(block)
            if frame is None:
                # Pass keepalives through unchanged by emitting a "blank"
                # frame whose raw_bytes is the original block + terminator.
                yield SSEFrame(event=None, data_raw="", raw_bytes=block + terminator)
            else:
                # Re-attach the actual upstream terminator so wire bytes
                # round-trip exactly.
                frame.raw_bytes = block + terminator
                yield frame
