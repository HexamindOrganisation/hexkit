"""Pick the agent implementation for a request.

The roster declares each agent's `framework`; that drives which reference agent
runs (so the agent emits the matching framework's native events). The `native`
agent uses the deterministic echo, or the optional OpenAI-backed `LLMAgent` when
`AGENT_ENABLE_LLM=1` and a key is forwarded.
"""

from __future__ import annotations

import os
from functools import partial
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

    # A real OpenAI Agents SDK agent (not a canned demo). Routed by id so the
    # `openai-agents` framework still maps to the demo agent (Forge) for others.
    # The agent + its invocation helpers live in `healthcare_agent` (pure SDK);
    # `OpenAIAgentsAgent` is the reusable framework→contract bridge. Here we just
    # pick the streamer: plain SDK, or the HexGate-wrapped `run_as` (opt-in via
    # HEALTHCARE_HEXGATE; role via HEALTHCARE_ROLE, default `nurse`). Lazy import
    # so a missing `openai-agents`/`hexgate` install doesn't break the roster.
    if agent_id == "healthcare":
        from . import healthcare_agent
        from .openai_agents import OpenAIAgentsAgent, hexgate_api_key

        if os.getenv("HEALTHCARE_HEXGATE", "0") == "1":
            role = os.getenv("HEALTHCARE_ROLE", "nurse")
            streamer = partial(
                healthcare_agent.run_as, role=role, api_key=hexgate_api_key()
            )
        else:
            streamer = healthcare_agent.run
        return OpenAIAgentsAgent(streamer)

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
