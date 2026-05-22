from __future__ import annotations

import pytest

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from platform_runtime.adapters.langchain_adapter import translate_input

def test_empty_messages_returns_empty():
    assert translate_input({"messages": []}) == {"messages": []}

def test_single_human_message():
    input = {"messages": [{"role": "user", "content": "Hello"}]}
    assert translate_input(input) == {"messages": [HumanMessage(content="Hello")]}

def test_single_ai_message():
    input = {"messages": [{"role": "assistant", "content": "Hi there!"}]}
    assert translate_input(input) == {"messages": [AIMessage(content="Hi there!")]}

def test_single_system_message():
    input = {"messages": [{"role": "system", "content": "System notice"}]}
    assert translate_input(input) == {"messages": [SystemMessage(content="System notice")]}

def test_mixed_messages():
    input = {
        "messages": [
            {"role": "system", "content": "System notice"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
    }
    assert translate_input(input) == {
        "messages": [
            SystemMessage(content="System notice"),
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
        ]
    }
