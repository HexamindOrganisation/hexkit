"""
OpenAI Agents adapter: framework recognition, registration, and the parts of
the protocol that don't require API credentials (`tools`, `metadata`,
`health`). The actual streaming path needs OPENAI_API_KEY and isn't
covered here — it's exercised by the LangChain analog and the wire protocol
is framework-agnostic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from platform_runtime.adapters import (
    get_adapter_class,
    openai_agents_adapter,  # noqa: F401 — import for side-effect registration
)
from platform_runtime.adapters.openai_agents_adapter import OpenAIAgentsAdapter
from platform_runtime.manifest import SUPPORTED_FRAMEWORKS
from platform_runtime.registry import AgentRegistry


EXAMPLE_AGENT = (
    Path(__file__).resolve().parents[1] / "examples" / "openai_agents_hello"
)


def test_framework_listed_as_supported() -> None:
    assert "openai-agents" in SUPPORTED_FRAMEWORKS


def test_adapter_registered() -> None:
    cls = get_adapter_class("openai-agents")
    assert cls is OpenAIAgentsAdapter


@pytest.mark.asyncio
async def test_example_loads_and_introspects() -> None:
    """The bundled example agent should load in-process and expose its tool
    via the normalized `/tools` shape, without any API call."""
    reg = AgentRegistry()
    loaded = reg.load(EXAMPLE_AGENT)
    assert loaded.manifest.agent_id == "openai-hello"
    assert loaded.manifest.framework == "openai-agents"

    md = await loaded.runtime.metadata()
    assert md.framework == "openai-agents"
    assert md.capabilities.tools is True

    tools = await loaded.runtime.tools()
    assert len(tools) == 1
    assert tools[0].name == "get_current_time"
    # input_schema is the SDK's params_json_schema verbatim — a JSON Schema
    # object describing the tool's args.
    assert tools[0].input_schema.get("type") == "object"
    assert "timezone_name" in tools[0].input_schema.get("properties", {})

    h = await loaded.runtime.health()
    assert h.ok is True
