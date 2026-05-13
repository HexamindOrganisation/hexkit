"""
Example agent: a tiny LangChain tool-calling agent.

The platform calls `build_agent()` (named in agent.yaml under `agent_callable`)
and expects a LangChain `Runnable` back. Here we return an AgentExecutor that
binds one tool to a chat model.

Run it through the platform with:

    PLATFORM_AGENTS_DIR=examples \
        python -m platform_runtime
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


@tool
def get_current_time(timezone_name: str = "UTC") -> str:
    """Return the current time. `timezone_name` is informational only."""
    return f"{datetime.now(timezone.utc).isoformat()} ({timezone_name})"


def build_agent():
    """Factory: returns a LangChain Runnable (an AgentExecutor)."""
    model_name = os.environ.get("LANGCHAIN_HELLO_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(model=model_name, temperature=0, streaming=True)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a concise assistant. Use tools when helpful."),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )

    tools = [get_current_time]
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=False)
