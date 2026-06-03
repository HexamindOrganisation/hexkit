"""Registry: discovery, loading, duplicate detection, lookup."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from platform_runtime.registry import AgentRegistry, RegistryError


def test_load_single_agent(fake_agent_dir: Path) -> None:
    reg = AgentRegistry()
    loaded = reg.load(fake_agent_dir)
    assert loaded.manifest.agent_id == "my-fake"
    assert reg.get("my-fake") is loaded
    assert "my-fake" in reg


def test_duplicate_agent_id_rejected(fake_agent_dir: Path) -> None:
    reg = AgentRegistry()
    reg.load(fake_agent_dir)
    with pytest.raises(RegistryError, match="Duplicate"):
        reg.load(fake_agent_dir)


def test_discover_finds_nested(tmp_path: Path, fake_agent_dir: Path) -> None:
    # Move fake_agent_dir under a parent and add a sibling.
    parent = tmp_path / "agents"
    parent.mkdir()
    a = parent / "one"
    a.mkdir()
    (a / "agent.yaml").write_text(
        textwrap.dedent(
            """
            agent_id: one
            name: One
            framework: fake
            entrypoint: agent.py
            agent_callable: build_agent
            """
        ).lstrip()
    )
    (a / "agent.py").write_text("def build_agent(): return []\n")

    b = parent / "two"
    b.mkdir()
    (b / "agent.yaml").write_text(
        textwrap.dedent(
            """
            agent_id: two
            name: Two
            framework: fake
            entrypoint: agent.py
            agent_callable: build_agent
            """
        ).lstrip()
    )
    (b / "agent.py").write_text("def build_agent(): return []\n")

    reg = AgentRegistry()
    loaded = reg.discover(parent)
    ids = sorted(entry.manifest.agent_id for entry in loaded)
    assert ids == ["one", "two"]


def test_unknown_agent_id(fake_agent_dir: Path) -> None:
    reg = AgentRegistry()
    reg.load(fake_agent_dir)
    with pytest.raises(RegistryError, match="Unknown"):
        reg.get("nope")


def test_missing_callable(tmp_path: Path) -> None:
    a = tmp_path / "bad"
    a.mkdir()
    (a / "agent.yaml").write_text(
        textwrap.dedent(
            """
            agent_id: bad
            name: bad
            framework: fake
            entrypoint: agent.py
            agent_callable: missing_function
            """
        ).lstrip()
    )
    (a / "agent.py").write_text("def some_other(): pass\n")
    reg = AgentRegistry()
    with pytest.raises(RegistryError, match="no attribute"):
        reg.load(a)
