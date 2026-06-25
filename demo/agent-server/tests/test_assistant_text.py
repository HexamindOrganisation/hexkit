"""Unit tests for ``_assistant_text`` — the per-framework helper that extracts
assistant-text deltas from native events so the stream route can record the
reply into conversation memory. It mirrors the text shapes each translator reads
(CONTRACT §6); anything else must contribute nothing."""

from __future__ import annotations

import pytest
from agent_server.routes.agents import _assistant_text


def test_native_text_event():
    assert _assistant_text("native", {"type": "text", "text": "hello"}) == "hello"


def test_native_non_text_event_is_empty():
    assert _assistant_text("native", {"type": "tool", "id": "t1"}) == ""


@pytest.mark.parametrize("framework", ["langchain", "langgraph", "deepagents"])
def test_langchain_family_chat_model_stream(framework: str):
    ev = {"event": "on_chat_model_stream", "data": {"chunk": {"content": "chunk"}}}
    assert _assistant_text(framework, ev) == "chunk"


def test_langchain_non_string_content_is_empty():
    ev = {"event": "on_chat_model_stream", "data": {"chunk": {"content": [{"x": 1}]}}}
    assert _assistant_text("langchain", ev) == ""


def test_langchain_other_event_is_empty():
    assert _assistant_text("langchain", {"event": "on_tool_start"}) == ""


def test_openai_agents_output_text_delta():
    ev = {"type": "raw_response", "data": {"type": "response.output_text.delta", "delta": "tok"}}
    assert _assistant_text("openai-agents", ev) == "tok"


def test_openai_agents_other_event_is_empty():
    ev = {"type": "raw_response", "data": {"type": "response.completed"}}
    assert _assistant_text("openai-agents", ev) == ""


def test_google_adk_joins_part_texts():
    ev = {"content": {"parts": [{"text": "a"}, {"text": "b"}, {"foo": "ignored"}]}}
    assert _assistant_text("google-adk", ev) == "ab"


def test_google_adk_turn_complete_marker_is_skipped():
    # Avoid doubling: the final turn_complete frame re-sends accumulated text.
    ev = {"turn_complete": True, "content": {"parts": [{"text": "whole reply"}]}}
    assert _assistant_text("google-adk", ev) == ""


def test_unknown_framework_is_empty():
    assert _assistant_text("mystery", {"type": "text", "text": "x"}) == ""


def test_non_dict_event_is_empty():
    assert _assistant_text("native", "not a dict") == ""
