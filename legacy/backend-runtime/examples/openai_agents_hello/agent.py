"""
Example agent: a tiny OpenAI Agents SDK tool-calling agent.

The platform calls `build_agent()` (named in agent.yaml under
`agent_callable`) and expects an `agents.Agent` back.

Run it through the platform with:

    PLATFORM_AGENTS_DIR=examples \
        OPENAI_API_KEY=... \
        python -m platform_runtime
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from agents import Agent, function_tool


@function_tool
def get_current_time(timezone_name: str = "UTC") -> str:
    """Return the current time. `timezone_name` is informational only."""
    return f"{datetime.now(timezone.utc).isoformat()} ({timezone_name})"


def build_agent() -> Agent:
    """Factory: returns an OpenAI Agents SDK `Agent`."""
    return Agent(
        name="openai-hello",
        model=os.environ.get("OPENAI_HELLO_MODEL", "gpt-4o-mini"),
        instructions="You are a concise assistant. Use tools when helpful.",
        tools=[get_current_time],
    )
