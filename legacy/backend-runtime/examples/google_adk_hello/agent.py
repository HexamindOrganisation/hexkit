"""
Example agent: a tiny Google ADK tool-calling agent.

The platform calls `build_agent()` (named in agent.yaml under
`agent_callable`) and expects a `google.adk.Agent` back. The adapter wraps
it with a Runner internally — the agent author does not deal with sessions
or runners.

Run it through the platform with:

    PLATFORM_AGENTS_DIR=examples \
        GOOGLE_API_KEY=... \
        python -m platform_runtime
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from google.adk import Agent
from google.adk.tools import FunctionTool


def get_current_time(timezone_name: str = "UTC") -> str:
    """Return the current time. `timezone_name` is informational only."""
    return f"{datetime.now(timezone.utc).isoformat()} ({timezone_name})"


def build_agent() -> Agent:
    """Factory: returns a Google ADK `Agent`."""
    return Agent(
        name="adk_hello",
        model=os.environ.get("ADK_HELLO_MODEL", "gemini-2.5-flash"),
        instruction="You are a concise assistant. Use tools when helpful.",
        tools=[FunctionTool(get_current_time)],
    )
