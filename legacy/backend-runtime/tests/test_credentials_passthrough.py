"""
End-to-end-ish credentials passthrough at the adapter boundary.

The `CredentialsCache` unit tests prove the cache itself behaves correctly.
This file verifies that each framework adapter actually plugs the cache in,
so `request.context.credentials` reaches the factory. We invoke the adapter's
private `_get_*` accessor directly with a context dict — no model client is
ever instantiated, so these tests don't need API keys or network.

Skipping rules: each test imports its adapter; if the framework extra is
missing in this environment we mark it `skip`. The LangChain extra is the
one present in the standard runtime venv, so it's exercised by default.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from platform_runtime.manifest import AgentManifest
from platform_runtime.protocol import AgentCapabilities, Credentials


def _manifest(framework: str) -> AgentManifest:
    return AgentManifest(
        agent_id="creds-test",
        name="Creds Test",
        framework=framework,
        entrypoint="agent.py",
        agent_callable="build_agent",
        version="0.1.0",
        capabilities=AgentCapabilities(),
    )


async def test_langchain_adapter_threads_credentials_to_factory() -> None:
    try:
        from langchain_core.runnables import RunnableLambda
    except ImportError:
        pytest.skip("LangChain extra not installed")
    from platform_runtime.adapters.langchain_adapter import LangChainAdapter

    received: list[Credentials | None] = []

    def factory(credentials=None):
        received.append(credentials)
        return RunnableLambda(lambda x: x)

    adapter = LangChainAdapter(
        manifest=_manifest("langchain"), root=Path("."), factory=factory
    )

    # No-credentials context → factory called with credentials=None.
    await adapter._get_runnable({})
    assert received == [None]

    # Context with credentials → factory called with a Credentials instance
    # carrying the same values.
    await adapter._get_runnable(
        {"credentials": {"openai_api_key": "sk-test"}}
    )
    assert received[1] is not None
    assert received[1].openai_api_key == "sk-test"

    # Same credentials again → cache hit, factory NOT called.
    await adapter._get_runnable(
        {"credentials": {"openai_api_key": "sk-test"}}
    )
    assert len(received) == 2


async def test_openai_agents_adapter_threads_credentials_to_factory() -> None:
    try:
        from agents import Agent
    except ImportError:
        pytest.skip("openai-agents extra not installed")
    from platform_runtime.adapters.openai_agents_adapter import (
        OpenAIAgentsAdapter,
    )

    received: list[Credentials | None] = []

    def factory(credentials=None):
        received.append(credentials)
        return Agent(name="creds-test", instructions="noop")

    adapter = OpenAIAgentsAdapter(
        manifest=_manifest("openai-agents"), root=Path("."), factory=factory
    )

    await adapter._get_agent({"credentials": {"openai_api_key": "sk-x"}})
    assert received[0].openai_api_key == "sk-x"


async def test_google_adk_adapter_threads_credentials_to_factory() -> None:
    try:
        from google.adk import Agent
    except ImportError:
        pytest.skip("google-adk extra not installed")
    from platform_runtime.adapters.google_adk_adapter import GoogleADKAdapter

    received: list[Credentials | None] = []

    def factory(credentials=None):
        received.append(credentials)
        return Agent(name="creds_test")

    adapter = GoogleADKAdapter(
        manifest=_manifest("google-adk"), root=Path("."), factory=factory
    )

    await adapter._get_runner({"credentials": {"google_api_key": "AIz-x"}})
    assert received[0].google_api_key == "AIz-x"
