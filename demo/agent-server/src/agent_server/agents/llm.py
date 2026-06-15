"""Optional OpenAI-backed `native` agent.

Streams real model tokens as minimal ``text`` events (framework `native`). The
selector (`agents.select`) returns this only when ``AGENT_ENABLE_LLM=1`` and an
``OPENAI_API_KEY`` is set in the backend's environment; otherwise the
deterministic `EchoAgent` runs. Shows how a real agent reads its provider key
from its own env with minimal plumbing.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from .. import protocol

logger = logging.getLogger("agent_server.llm")


def _log_prompt(messages: list[dict]) -> None:
    """Log the full prompt sent to the model — every message, untruncated,
    including the system block with inlined file contents. Verbose by design:
    it's the ground truth for "did my file's text actually reach the model?"."""
    lines = [f"LLM prompt ({len(messages)} message(s)):"]
    for m in messages:
        lines.append(f"  ── [{m.get('role')}] ──")
        lines.append(str(m.get("content", "")))
    logger.info("\n".join(lines))


class LLMAgent:
    """Streams a real OpenAI completion as text events, falling back on failure."""

    framework = "native"

    async def run(
        self,
        *,
        input: dict[str, Any],
        context: dict[str, Any],
    ) -> AsyncIterator[dict]:
        query = protocol.last_user_text(input)
        api_key = os.getenv("OPENAI_API_KEY")
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=api_key)
            messages = (input or {}).get("messages") or [
                {"role": "user", "content": query}
            ]
            # Attached files persist across the conversation — inline their text
            # as a leading system message so the model can use them.
            files = (context or {}).get("files") or []
            blocks = [
                f"## {f.get('name', 'file')}\n{f.get('content') or '[binary file omitted]'}"
                for f in files
            ]
            if blocks:
                messages = [
                    {
                        "role": "system",
                        "content": "The user attached these files:\n\n"
                        + "\n\n".join(blocks),
                    },
                    *messages,
                ]
            _log_prompt(messages)
            stream = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield protocol.text(delta)
        except Exception as e:  # noqa: BLE001 — degrade to a visible text event
            yield protocol.text(f"[llm unavailable: {e}] echo: {query}")
