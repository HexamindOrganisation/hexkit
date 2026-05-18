"""
Example: a tiny DeepAgents agent.

`create_deep_agent` returns a compiled LangGraph, so the platform serves it
through the existing LangChain adapter — no DeepAgents-specific runtime code.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from deepagents import create_deep_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


@tool
def get_current_time(timezone_name: str = "UTC") -> str:
    """Return the current time."""
    return f"{datetime.now(timezone.utc).isoformat()} ({timezone_name})"


def build_agent():
    """Factory: returns a compiled DeepAgents graph."""
    return create_deep_agent(
        model=ChatOpenAI(
            model=os.environ.get("DEEPAGENTS_HELLO_MODEL", "gpt-4o-mini"),
            temperature=0,
            streaming=True,
        ),
        tools=[get_current_time],
        system_prompt="You are concise. Use tools when helpful.",
    )
