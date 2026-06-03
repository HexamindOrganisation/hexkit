"""Optional Gemini-backed `google-adk` agent (Orbit).

The google-adk analogue of `llm.py` (Probe/OpenAI): when ``AGENT_ENABLE_LLM`` is
set AND a ``google_api_key`` is forwarded, it streams a real Gemini completion
and **projects each chunk into google-adk-native ``Event`` shapes**, so the
proxy's google-adk translator normalizes it exactly as it would a real ADK
runtime. The selector (`agents.select`) returns this only under those conditions;
otherwise the deterministic `GoogleADKDemoAgent` (canned ADK events) runs.

On any failure (package missing, bad key, …) it degrades to a single visible
text event rather than crashing — same contract as `LLMAgent`.

Needs the `google-genai` package in the run venv and a Google key set in
Settings (provider `google`).
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, AsyncIterator

from .. import protocol

logger = logging.getLogger("agent_server.adk")

_MODEL = "gemini-2.0-flash"


def _build_prompt(input: dict[str, Any], files: list[dict], query: str) -> str:
    """Flatten the transcript (+ any attached file text) into a single prompt.

    Mirrors `LLMAgent`'s inlining: attached files' decoded text leads, then the
    conversation. Gemini accepts a plain string for `contents`."""
    messages = (input or {}).get("messages") or [{"role": "user", "content": query}]
    parts: list[str] = []
    blocks = [
        f"## {f.get('name', 'file')}\n{f.get('content') or '[binary file omitted]'}"
        for f in files
    ]
    if blocks:
        parts.append("The user attached these files:\n\n" + "\n\n".join(blocks))
    for m in messages:
        who = "User" if m.get("role") == "user" else "Assistant"
        parts.append(f"{who}: {m.get('content', '')}")
    parts.append("Assistant:")
    return "\n\n".join(parts)


def _log_prompt(prompt: str) -> None:
    logger.info("ADK/Gemini prompt:\n%s", prompt)


class GoogleADKAgent:
    """Streams a real Gemini completion as google-adk `Event` projections."""

    framework = "google-adk"

    async def run(
        self,
        *,
        input: dict[str, Any],
        context: dict[str, Any],
    ) -> AsyncIterator[dict]:
        query = protocol.last_user_text(input)
        creds = (context or {}).get("credentials") or {}
        api_key = creds.get("google_api_key")
        files = (context or {}).get("files") or []
        author = "assistant"

        try:
            from google import genai

            client = genai.Client(api_key=api_key)
            prompt = _build_prompt(input, files, query)
            _log_prompt(prompt)

            # The async streaming entrypoint returns either an async iterator or
            # a coroutine resolving to one, depending on the SDK version — handle
            # both so we don't break on a minor API shift.
            maybe = client.aio.models.generate_content_stream(
                model=_MODEL, contents=prompt
            )
            stream = await maybe if inspect.isawaitable(maybe) else maybe

            async for chunk in stream:
                text = getattr(chunk, "text", None)
                if text:
                    yield {
                        "author": author,
                        "partial": True,
                        "content": {"parts": [{"text": text}]},
                    }
            # Close the streamed text block for the translator.
            yield {"author": author, "turn_complete": True, "content": {"parts": []}}
        except Exception as e:  # noqa: BLE001 — degrade to a visible text event
            yield {
                "author": author,
                "partial": True,
                "content": {"parts": [{"text": f"[gemini unavailable: {e}] echo: {query}"}]},
            }
            yield {"author": author, "turn_complete": True, "content": {"parts": []}}
