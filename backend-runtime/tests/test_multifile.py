"""
Multi-file agent source: agents can ship helper modules alongside the
entrypoint, in both flat layouts and subfolder-package layouts.

These tests use the `fake` framework so no real LangChain code is exercised.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from platform_runtime.registry import AgentRegistry


def test_flat_layout_sibling_imports(tmp_path: Path) -> None:
    """Entrypoint in the manifest dir importing a sibling module."""
    agent_dir = tmp_path / "flat"
    agent_dir.mkdir()
    (agent_dir / "agent.yaml").write_text(
        textwrap.dedent(
            """
            agent_id: flat-agent
            name: Flat Layout
            framework: fake
            entrypoint: agent.py
            agent_callable: build_agent
            """
        ).lstrip()
    )
    (agent_dir / "helpers.py").write_text(
        "def script() -> list:\n"
        "    return [('delta', {'message_id': 'm', 'delta': 'from-helper'})]\n"
    )
    (agent_dir / "agent.py").write_text(
        "from helpers import script\n"
        "def build_agent():\n"
        "    return script()\n"
    )

    reg = AgentRegistry()
    loaded = reg.load(agent_dir)
    assert loaded.manifest.agent_id == "flat-agent"


def test_subfolder_package_layout(tmp_path: Path) -> None:
    """Entrypoint inside a subfolder package. Both absolute (`from pkg.x`)
    and script-style (`from x`) sibling imports must work."""
    agent_dir = tmp_path / "pkg-agent"
    agent_dir.mkdir()
    pkg = agent_dir / "app"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "tools.py").write_text("VALUE = 42\n")
    (pkg / "shared.py").write_text("def hello() -> str: return 'hi'\n")

    (agent_dir / "agent.yaml").write_text(
        textwrap.dedent(
            """
            agent_id: pkg-agent
            name: Package Layout
            framework: fake
            entrypoint: app/main.py
            agent_callable: build_agent
            """
        ).lstrip()
    )
    (pkg / "main.py").write_text(
        # Absolute (manifest-rooted) AND script-style (entrypoint-dir-rooted)
        # imports — both must resolve.
        "from app.tools import VALUE\n"
        "from shared import hello\n"
        "def build_agent():\n"
        "    assert VALUE == 42 and hello() == 'hi'\n"
        "    return [('delta', {'message_id': 'm', 'delta': 'ok'})]\n"
    )

    reg = AgentRegistry()
    loaded = reg.load(agent_dir)
    assert loaded.manifest.agent_id == "pkg-agent"


def test_two_agents_with_same_filename_do_not_collide(tmp_path: Path) -> None:
    """Two agents named `agent.py` in different dirs must not shadow each
    other in `sys.modules`. They're loaded under namespaced synthetic names."""
    for agent_id, msg in [("first", "hello-1"), ("second", "hello-2")]:
        d = tmp_path / agent_id
        d.mkdir()
        (d / "agent.yaml").write_text(
            textwrap.dedent(
                f"""
                agent_id: {agent_id}
                name: {agent_id}
                framework: fake
                entrypoint: agent.py
                agent_callable: build_agent
                """
            ).lstrip()
        )
        (d / "agent.py").write_text(
            f"def build_agent(): return [('delta', "
            f"{{'message_id': 'm', 'delta': '{msg}'}})]\n"
        )

    reg = AgentRegistry()
    reg.load(tmp_path / "first")
    reg.load(tmp_path / "second")
    assert {a.manifest.agent_id for a in reg.list()} == {"first", "second"}
