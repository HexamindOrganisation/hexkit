"""The reference echo agent — the deterministic, no-dependency baseline.

Note how little it has to do: yield plain text chunks and a tool call. No run
ids, no sequence numbers, no block lifecycle — the proxy synthesizes all of
that. It word-chunks the last user message back, then fires one sample tool
call routed to the ``tool-calls`` widget. Per-chunk sleeps make cancellation
observable mid-stream.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from .. import protocol
from ..tools import fake_search

_CHUNK_DELAY = 0.12


class EchoAgent:
    framework = "native"

    async def run(
        self,
        *,
        input: dict[str, Any],
        context: dict[str, Any],
    ) -> AsyncIterator[dict]:
        query = protocol.last_user_text(input)

        files = (context or {}).get("files") or []

        # Echo a short content preview so it's visible the bytes actually arrived.
        def _preview(f: dict) -> str:
            c = (f.get("content") or "").strip().replace("\n", " ")
            name = f.get("name", "?")
            return f'{name}="{c[:60]}"' if c else f"{name}(binary)"

        files_note = (
            "files{ " + "; ".join(_preview(f) for f in files) + " } | " if files else ""
        )
        reply = f"{files_note}echo: {query}".strip()

        for word in reply.split(" "):
            await asyncio.sleep(_CHUNK_DELAY)
            yield protocol.text(word + " ")

        # One sample tool call, routed to the `tool-calls` widget.
        yield protocol.tool("t1", "search", {"q": query}, widget="tool-calls")
        await asyncio.sleep(_CHUNK_DELAY)
        yield protocol.tool_result("t1", output=fake_search(query))
