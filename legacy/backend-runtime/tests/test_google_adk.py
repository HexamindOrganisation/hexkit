"""
Google ADK adapter: framework recognition, registration, and the parts of
the protocol that don't require credentials (`tools`, `metadata`, `health`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from platform_runtime.adapters import (
    get_adapter_class,
    google_adk_adapter,  # noqa: F401 — import for side-effect registration
)
from platform_runtime.adapters.google_adk_adapter import GoogleADKAdapter
from platform_runtime.manifest import SUPPORTED_FRAMEWORKS
from platform_runtime.registry import AgentRegistry


EXAMPLE_AGENT = (
    Path(__file__).resolve().parents[1] / "examples" / "google_adk_hello"
)


def test_framework_listed_as_supported() -> None:
    assert "google-adk" in SUPPORTED_FRAMEWORKS


def test_adapter_registered() -> None:
    cls = get_adapter_class("google-adk")
    assert cls is GoogleADKAdapter


@pytest.mark.asyncio
async def test_example_loads_and_introspects() -> None:
    """The bundled example agent should load in-process and expose its tool
    via the normalized `/tools` shape, without any API call."""
    reg = AgentRegistry()
    loaded = reg.load(EXAMPLE_AGENT)
    assert loaded.manifest.agent_id == "adk-hello"
    assert loaded.manifest.framework == "google-adk"

    md = await loaded.runtime.metadata()
    assert md.framework == "google-adk"
    assert md.capabilities.tools is True

    tools = await loaded.runtime.tools()
    assert len(tools) == 1
    assert tools[0].name == "get_current_time"
    # Schema is translated from ADK's `Schema` to JSON Schema form.
    schema = tools[0].input_schema
    assert schema.get("type") == "object"
    assert "timezone_name" in schema.get("properties", {})
    assert schema["properties"]["timezone_name"].get("type") == "string"

    h = await loaded.runtime.health()
    assert h.ok is True
