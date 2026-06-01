"""The reference echo agent — the deterministic, no-dependency baseline.

Note how little it has to do: yield plain text chunks and a tool call. No run
ids, no sequence numbers, no block lifecycle — the proxy synthesizes all of
that. It word-chunks the last user message back, prefixed with
``creds-present:{bool}`` so a smoke test can confirm the proxy forwarded the
developer's secrets, then fires one sample tool call routed to the
``tool-calls`` widget. Per-chunk sleeps make cancellation observable mid-stream.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

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

        creds = (context or {}).get("credentials") or {}
        present = bool(creds.get("openai_api_key"))
        reply = f"creds-present:{present} | echo: {query}".strip()

        for word in reply.split(" "):
            await asyncio.sleep(_CHUNK_DELAY)
            yield protocol.text(word + " ")

        # One sample tool call, routed to the `tool-calls` widget.
        yield protocol.tool("t1", "search", {"q": query}, widget="tool-calls")
        await asyncio.sleep(_CHUNK_DELAY)
        yield protocol.tool_result("t1", output=fake_search(query))
