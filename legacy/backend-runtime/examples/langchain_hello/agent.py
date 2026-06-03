"""
Example agent: a tiny LangChain tool-calling agent.

The platform calls `build_agent()` (named in agent.yaml under `agent_callable`)
and expects a LangChain `Runnable` back. In LangChain 1.x the canonical agent
constructor is `create_agent`, which returns a compiled LangGraph (a Runnable).

Run it through the platform with:

    PLATFORM_AGENTS_DIR=examples \
        python -m platform_runtime
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


@tool
def get_current_time(timezone_name: str = "UTC") -> str:
    """Return the current time. `timezone_name` is informational only."""
    return f"{datetime.now(timezone.utc).isoformat()} ({timezone_name})"


def build_agent():
    """Factory: returns a LangChain Runnable (a compiled LangGraph agent)."""
    model_name = os.environ.get("LANGCHAIN_HELLO_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(model=model_name, temperature=0, streaming=True)

    return create_agent(
        model=llm,
        tools=[get_current_time],
        system_prompt="You are a concise assistant. Use tools when helpful.",
    )
