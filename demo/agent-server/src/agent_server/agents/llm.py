"""Optional OpenAI-backed `native` agent.

Streams real model tokens as minimal ``text`` events (framework `native`). The
selector (`agents.select`) returns this only when ``AGENT_ENABLE_LLM=1`` and the
proxy forwarded an ``openai_api_key``; otherwise the deterministic `EchoAgent`
runs. Shows how a real agent consumes a forwarded secret with minimal plumbing.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from .. import protocol


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
        api_key = ((context or {}).get("credentials") or {}).get("openai_api_key")
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=api_key)
            messages = (input or {}).get("messages") or [
                {"role": "user", "content": query}
            ]
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
