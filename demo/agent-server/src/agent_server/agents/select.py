"""Pick the agent implementation for a request.

The roster declares each agent's `framework`; that drives which reference agent
runs (so the agent emits the matching framework's native events). The `native`
agent uses the deterministic echo, or the optional OpenAI-backed `LLMAgent` when
`AGENT_ENABLE_LLM=1` and a key is forwarded.
"""

from __future__ import annotations

from typing import Any

from ..config import get_settings
from ..roster import get_agent
from .base import Agent
from .demos import GoogleADKDemoAgent, LangChainDemoAgent, OpenAIAgentsDemoAgent
from .echo import EchoAgent
from .llm import LLMAgent


def select_agent(agent_id: str, context: dict[str, Any]) -> Agent:
    framework = (get_agent(agent_id) or {}).get("framework", "native")

    if framework == "langchain":
        return LangChainDemoAgent()
    if framework == "openai-agents":
        return OpenAIAgentsDemoAgent()
    if framework == "google-adk":
        return GoogleADKDemoAgent()

    # native: deterministic echo, or real OpenAI when enabled + key present.
    creds = (context or {}).get("credentials") or {}
    if get_settings().enable_llm and creds.get("openai_api_key"):
        return LLMAgent()
    return EchoAgent()
