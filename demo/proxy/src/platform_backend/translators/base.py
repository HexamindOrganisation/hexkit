"""Translator base + shared helpers.

A translator turns a developer backend's **framework-native** events (serialized
to JSON, one per wire frame) into the rich internal event schema, by driving a
shared :class:`~hexa_events.RunEmitter`. It holds only framework-specific
per-run bookkeeping (tool-id maps, open-block keys); the run envelope
(``run_start`` / ``run_end``) is owned by the chat route, which creates the
emitter and calls ``handle`` per frame.

The proxy never imports langchain / openai / adk — translators pattern-match on
the *shape* of the serialized native events. The framework library lives in the
developer's process, where the agent actually runs.
"""

from __future__ import annotations

from typing import Any

from hexa_events import RunEmitter, StreamEvent

# Tool routing note: translators leave `widget` as None (the default target).
# The proxy does NOT name a UI widget — the frontend resolves the default to
# whatever widget has type `tool-calls`, so a dev can name that widget anything.
# A translator only sets `widget` to a concrete name when the framework's native
# event explicitly targets one (today only the `native` format can).


class BaseTranslator:
    """One instance per run. Subclasses implement :meth:`handle`."""

    def handle(self, emitter: RunEmitter, event: dict[str, Any]) -> list[StreamEvent]:
        raise NotImplementedError


def extract_text(obj: Any) -> str:
    """Pull printable text from a serialized chunk / message / content dict.

    Mirrors the LangChain/ADK adapters' text extraction but operates on the
    JSON projection (no live framework objects): a string, a ``{"content": ...}``
    dict (str or multimodal part list), or a ``{"text": ...}`` part.
    """
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        content = obj.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text" and isinstance(part.get("text"), str):
                        parts.append(part["text"])
                    elif isinstance(part.get("text"), str):
                        parts.append(part["text"])
            return "".join(parts)
        if isinstance(obj.get("text"), str):
            return obj["text"]
    return ""


def coerce_args(value: Any) -> dict[str, Any]:
    """Coerce a tool-arguments payload into a dict (JSON-string tolerated)."""
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    if isinstance(value, str):
        import json

        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except (json.JSONDecodeError, ValueError):
            return {"value": value}
    return {"value": value}
