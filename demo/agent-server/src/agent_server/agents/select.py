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
from .adk_llm import GoogleADKAgent
from .base import Agent
from .demos import GoogleADKDemoAgent, LangChainDemoAgent, OpenAIAgentsDemoAgent
from .echo import EchoAgent
from .llm import LLMAgent


def select_agent(agent_id: str, context: dict[str, Any]) -> Agent:
    framework = (get_agent(agent_id) or {}).get("framework", "native")
    creds = (context or {}).get("credentials") or {}
    llm_on = get_settings().enable_llm

    # Real OpenAI Agents SDK agent (it picks the plain vs HexGate path itself).
    # Lazy import so a missing openai-agents/hexgate install doesn't break the roster.
    if agent_id == "healthcare":
        from .healthcare import HealthcareAgent

        return HealthcareAgent()

    if agent_id == "devops":
        from .devops import DevopsAgent

        return DevopsAgent()

    if framework == "langchain":
        return LangChainDemoAgent()
    if framework == "openai-agents":
        return OpenAIAgentsDemoAgent()
    if framework == "google-adk":
        # Real Gemini via Google ADK when enabled + a google key is forwarded;
        # otherwise the deterministic canned ADK events.
        if llm_on and creds.get("google_api_key"):
            return GoogleADKAgent()
        return GoogleADKDemoAgent()

    # native: deterministic echo, or real OpenAI when enabled + key present.
    if llm_on and creds.get("openai_api_key"):
        return LLMAgent()
    return EchoAgent()
