"""Reference agents that emit *framework-native* event shapes.

These don't run real LangChain/OpenAI/ADK agents (that would need the libraries
+ live models). They emit the JSON projection of each framework's native event
stream — exactly what a developer's thin server layer forwards after running
their real agent — so the proxy's per-framework translators are exercised
end to end. Each yields a representative sequence: streamed text, then one tool
call + result. Per-chunk sleeps make cancellation observable.

A real developer would write, e.g.::

    async def run(self, *, input, context):
        async for ev in my_langchain_runnable.astream_events(.., version="v2"):
            yield hexa_forward(ev)   # JSON-project the native event

and the proxy does the rest.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from .. import protocol
from ..tools import fake_search

_CHUNK_DELAY = 0.12


class LangChainDemoAgent:
    """Emits LangChain `astream_events(v2)` projections."""

    framework = "langchain"

    async def run(
        self, *, input: dict[str, Any], context: dict[str, Any]
    ) -> AsyncIterator[dict]:
        query = protocol.last_user_text(input)
        rid = "model-1"
        for word in f"LangChain echo: {query}".split(" "):
            await asyncio.sleep(_CHUNK_DELAY)
            yield {
                "event": "on_chat_model_stream",
                "run_id": rid,
                "name": "chat",
                "data": {"chunk": {"content": word + " "}},
            }
        yield {"event": "on_chat_model_end", "run_id": rid, "data": {}}

        await asyncio.sleep(_CHUNK_DELAY)
        yield {
            "event": "on_tool_start",
            "run_id": "tool-1",
            "name": "search",
            "data": {"input": {"q": query}},
        }
        yield {
            "event": "on_tool_end",
            "run_id": "tool-1",
            "name": "search",
            "data": {"output": fake_search(query)},
        }


class OpenAIAgentsDemoAgent:
    """Emits OpenAI Agents SDK `stream_events()` projections."""

    framework = "openai-agents"

    async def run(
        self, *, input: dict[str, Any], context: dict[str, Any]
    ) -> AsyncIterator[dict]:
        query = protocol.last_user_text(input)
        text = f"OpenAI echo: {query}"
        for word in text.split(" "):
            await asyncio.sleep(_CHUNK_DELAY)
            yield {
                "type": "raw_response",
                "data": {"type": "response.output_text.delta", "delta": word + " "},
            }
        yield {
            "type": "run_item",
            "name": "message_output_created",
            "item": {"raw_item": {"content": [{"text": text}]}},
        }

        await asyncio.sleep(_CHUNK_DELAY)
        yield {
            "type": "run_item",
            "name": "tool_called",
            "item": {"raw_item": {"call_id": "c1", "name": "search",
                                  "arguments": f'{{"q": "{query}"}}'}},
        }
        yield {
            "type": "run_item",
            "name": "tool_output",
            "item": {"raw_item": {"call_id": "c1", "name": "search"},
                     "output": fake_search(query)},
        }


class GoogleADKDemoAgent:
    """Emits Google ADK `Event` projections."""

    framework = "google-adk"

    async def run(
        self, *, input: dict[str, Any], context: dict[str, Any]
    ) -> AsyncIterator[dict]:
        query = protocol.last_user_text(input)
        author = "assistant"
        for word in f"ADK echo: {query}".split(" "):
            await asyncio.sleep(_CHUNK_DELAY)
            yield {
                "author": author,
                "partial": True,
                "content": {"parts": [{"text": word + " "}]},
            }
        # function_call auto-closes the streamed text block in the emitter.
        await asyncio.sleep(_CHUNK_DELAY)
        yield {
            "author": author,
            "content": {"parts": [{"function_call": {"id": "c1", "name": "search",
                                                      "args": {"q": query}}}]},
        }
        yield {
            "author": author,
            "content": {"parts": [{"function_response": {"id": "c1", "name": "search",
                                                         "response": fake_search(query)}}]},
        }
