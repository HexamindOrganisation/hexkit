"""
VenvManager: cache-key behavior and end-to-end venv materialization.

The "slow" test actually builds a venv and is gated behind the `slow` marker
because it takes 30-90s (pip resolves transitive deps; uv is much faster).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from platform_runtime.manifest import AgentManifest, load_manifest
from platform_runtime.venv_manager import VenvManager


def _write_manifest(
    agent_dir: Path,
    *,
    agent_id: str = "needs-deps",
    requirements: list[str] | None = None,
) -> AgentManifest:
    agent_dir.mkdir(parents=True, exist_ok=True)
    reqs_block = ""
    if requirements:
        reqs_block = "requirements:\n" + "".join(f"  - {r}\n" for r in requirements)
    (agent_dir / "agent.yaml").write_text(
        textwrap.dedent(
            f"""
            agent_id: {agent_id}
            name: {agent_id}
            framework: fake
            entrypoint: agent.py
            agent_callable: build_agent
            """
        ).lstrip()
        + reqs_block
    )
    (agent_dir / "agent.py").write_text("def build_agent(): return []\n")
    manifest, _ = load_manifest(agent_dir)
    return manifest


def test_no_requirements_returns_none(tmp_path: Path) -> None:
    """An agent without `requirements:` should never trigger a venv build."""
    manifest = _write_manifest(tmp_path / "a", requirements=None)
    vm = VenvManager(cache_dir=tmp_path / "cache")
    assert vm.ensure_venv(manifest, tmp_path / "a") is None
    # Cache dir is created (mkdir in __init__) but contains no venv.
    assert list((tmp_path / "cache").iterdir()) == []


def test_cache_key_changes_with_requirements(tmp_path: Path) -> None:
    """Different requirements ⇒ different cache key ⇒ different venv path."""
    m1 = _write_manifest(
        tmp_path / "a1", agent_id="a", requirements=["rich==13.0.0"]
    )
    m2 = _write_manifest(
        tmp_path / "a2", agent_id="a", requirements=["rich==13.1.0"]
    )
    k1 = VenvManager._cache_key(m1)
    k2 = VenvManager._cache_key(m2)
    assert k1 != k2


def test_cache_key_stable_for_same_inputs(tmp_path: Path) -> None:
    m1 = _write_manifest(
        tmp_path / "a", agent_id="a", requirements=["rich", "httpx"]
    )
    # Same manifest reloaded — same key.
    m1_reload, _ = load_manifest(tmp_path / "a")
    assert VenvManager._cache_key(m1) == VenvManager._cache_key(m1_reload)


@pytest.mark.slow
def test_end_to_end_venv_build(tmp_path: Path) -> None:
    """Materialize a real venv with a tiny dependency and verify reuse.

    `six` is chosen because it's tiny, has no transitive deps, and installs
    in a second or two even via pip.
    """
    manifest = _write_manifest(
        tmp_path / "a",
        agent_id="slow-venv",
        requirements=["six==1.16.0"],
    )

    vm = VenvManager(cache_dir=tmp_path / "cache")
    python = vm.ensure_venv(manifest, tmp_path / "a")
    assert python is not None
    assert python.is_file()

    # Reuse: second call must NOT rebuild. We assert by checking that the
    # ready-marker mtime is unchanged.
    marker = python.parent.parent / ".platform_runtime_ready"
    mtime_before = marker.stat().st_mtime
    python2 = vm.ensure_venv(manifest, tmp_path / "a")
    assert python2 == python
    assert marker.stat().st_mtime == mtime_before
