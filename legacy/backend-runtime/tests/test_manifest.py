"""Manifest loader: validates the file format and resolution rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from platform_runtime.manifest import (
    AgentManifest,
    ManifestError,
    load_manifest,
)


def test_loads_valid_manifest(fake_agent_dir: Path) -> None:
    manifest, root = load_manifest(fake_agent_dir)
    assert isinstance(manifest, AgentManifest)
    assert manifest.agent_id == "my-fake"
    assert manifest.framework == "fake"
    assert root == fake_agent_dir.resolve()
    assert manifest.resolved_entrypoint(root) == (fake_agent_dir / "agent.py").resolve()


def test_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="not found"):
        load_manifest(tmp_path / "does-not-exist")


def test_missing_manifest_file(tmp_path: Path) -> None:
    (tmp_path / "no-yaml").mkdir()
    with pytest.raises(ManifestError, match="No agent.yaml"):
        load_manifest(tmp_path / "no-yaml")


def test_unsupported_framework(tmp_path: Path) -> None:
    agent = tmp_path / "bad"
    agent.mkdir()
    (agent / "agent.yaml").write_text(
        "agent_id: bad\nname: x\nframework: martian\n"
        "entrypoint: agent.py\nagent_callable: f\n"
    )
    (agent / "agent.py").write_text("def f(): pass\n")
    with pytest.raises(ManifestError, match="not supported"):
        load_manifest(agent)


def test_missing_entrypoint_file(tmp_path: Path) -> None:
    agent = tmp_path / "noent"
    agent.mkdir()
    (agent / "agent.yaml").write_text(
        "agent_id: noent\nname: x\nframework: fake\n"
        "entrypoint: nope.py\nagent_callable: f\n"
    )
    with pytest.raises(ManifestError, match="not found"):
        load_manifest(agent)


def test_invalid_agent_id(tmp_path: Path) -> None:
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / "agent.yaml").write_text(
        "agent_id: 'has spaces'\nname: x\nframework: fake\n"
        "entrypoint: agent.py\nagent_callable: f\n"
    )
    (agent / "agent.py").write_text("def f(): pass\n")
    with pytest.raises(ManifestError, match="agent_id"):
        load_manifest(agent)
