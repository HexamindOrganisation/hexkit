"""
Framework aliasing: `langgraph` and `deepagents` are supported as
manifest framework names, both dispatching to the LangChain adapter.

These tests prove the alias mechanism and the end-to-end tools/metadata
path for bare LangGraph graphs. DeepAgents is identical at the adapter
level (returns a CompiledStateGraph), so its example test is gated behind
the `slow` marker because it pip-installs deepagents.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from platform_runtime.adapters import get_adapter_class
from platform_runtime.adapters.langchain_adapter import LangChainAdapter
from platform_runtime.manifest import SUPPORTED_FRAMEWORKS
from platform_runtime.registry import AgentRegistry


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_aliases_listed_as_supported() -> None:
    assert "langgraph" in SUPPORTED_FRAMEWORKS
    assert "deepagents" in SUPPORTED_FRAMEWORKS


def test_aliases_dispatch_to_langchain_adapter() -> None:
    """All three names resolve to the same adapter class."""
    base = get_adapter_class("langchain")
    assert get_adapter_class("langgraph") is base
    assert get_adapter_class("deepagents") is base
    assert base is LangChainAdapter


@pytest.mark.asyncio
async def test_langgraph_example_loads_and_introspects() -> None:
    """The bare-LangGraph example loads via the LangChain adapter and its
    tool is discoverable. No API call needed."""
    reg = AgentRegistry()
    loaded = reg.load(EXAMPLES / "langgraph_hello")
    assert loaded.manifest.framework == "langgraph"

    md = await loaded.runtime.metadata()
    assert md.framework == "langgraph"

    tools = await loaded.runtime.tools()
    assert [t.name for t in tools] == ["echo"]
    assert "text" in tools[0].input_schema.get("properties", {})
