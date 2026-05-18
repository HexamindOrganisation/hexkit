"""
Per-agent virtual environments.

When a manifest declares `requirements:`, the agent's worker is spawned with
its own Python interpreter that has those packages (and only those) installed.
This is what makes the spec's "dependency isolation" promise real: two agents
that depend on incompatible langchain versions can coexist because they don't
share a venv.

How it works
------------
1. We compute a cache key from the manifest (framework + sorted requirements
   + the absolute path of the platform-runtime source). The key changes if
   any input changes, so changing `requirements` rebuilds the venv but does
   NOT rebuild it on every server start.
2. The venv lives at `<cache_dir>/<agent_id>-<key>/`. Default cache dir is
   `~/.cache/platform_runtime/venvs`, overridable.
3. The venv is materialized via `uv` if available (Rust-fast), falling back
   to stdlib `venv` + `pip`. Both paths install:
       - platform-runtime itself (editable, pointing to the parent's source),
         so `python -m platform_runtime.worker` resolves inside the venv;
       - the framework extras (e.g. `[langchain]`) for the declared framework;
       - the agent's `requirements`.
4. A marker file is written when the install completes. Subsequent loads see
   the marker and skip reinstall — startup is fast on warm caches.

If `manifest.requirements` is empty, `ensure_venv` returns `None` and the
caller (the registry) keeps using `sys.executable`. No surprise venvs.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

from .manifest import AgentManifest


logger = logging.getLogger("platform_runtime.venv")


# Maps a framework name → the optional-extras key declared in our pyproject.
# Keeping it here (not in manifest.py) because it's a deployment concern,
# not part of the manifest schema.
FRAMEWORK_EXTRAS: dict[str, str] = {
    "langchain": "langchain",
    # LangGraph and DeepAgents are built on top of LangChain; reuse the
    # langchain extras group. Authors are free to list deepagents itself
    # under `requirements:` in their manifest if they need it installed.
    "langgraph": "langchain",
    "deepagents": "langchain",
    "openai-agents": "openai-agents",
    "google-adk": "google-adk",
}


DEFAULT_CACHE_DIR = Path.home() / ".cache" / "platform_runtime" / "venvs"

# Sentinel file inside a venv that records "install completed for this key".
_READY_MARKER = ".platform_runtime_ready"


class VenvError(Exception):
    """Raised when a per-agent venv cannot be created or populated."""


class VenvManager:
    """Builds and caches per-agent virtual environments."""

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ensure_venv(
        self, manifest: AgentManifest, root: Path
    ) -> Path | None:
        """Return path to the python interpreter for this agent's venv.

        Returns `None` when the manifest declares no requirements, signaling
        to callers that they should keep using the parent's interpreter.
        """
        if not manifest.requirements:
            return None

        key = self._cache_key(manifest)
        venv_dir = self.cache_dir / f"{manifest.agent_id}-{key}"
        python = _python_in_venv(venv_dir)

        if (venv_dir / _READY_MARKER).is_file() and python.is_file():
            logger.debug(
                "Reusing cached venv for agent_id=%s at %s",
                manifest.agent_id,
                venv_dir,
            )
            return python

        # Stale or absent: rebuild from scratch.
        if venv_dir.exists():
            logger.info("Rebuilding stale venv at %s", venv_dir)
            shutil.rmtree(venv_dir)

        logger.info(
            "Building venv for agent_id=%s framework=%s (%d requirement(s))",
            manifest.agent_id,
            manifest.framework,
            len(manifest.requirements),
        )
        try:
            self._create_venv(venv_dir)
            self._install_packages(python, manifest)
        except subprocess.CalledProcessError as e:
            raise VenvError(
                f"Failed to build venv for '{manifest.agent_id}': "
                f"{' '.join(map(str, e.cmd))} returned {e.returncode}\n"
                f"stderr: {e.stderr.decode('utf-8', errors='replace') if e.stderr else ''}"
            ) from e

        (venv_dir / _READY_MARKER).write_text(key, encoding="utf-8")
        return python

    # ------------------------------------------------------------------
    # Cache key
    # ------------------------------------------------------------------

    @staticmethod
    def _cache_key(manifest: AgentManifest) -> str:
        """Hash the inputs that should bust the cache.

        Includes the platform source path because we install platform-runtime
        editable from there; moving the source means existing venvs would
        reference a path that no longer exists.
        """
        h = hashlib.sha256()
        h.update(manifest.framework.encode())
        h.update(json.dumps(sorted(manifest.requirements)).encode())
        h.update(str(_platform_source_dir()).encode())
        return h.hexdigest()[:12]

    # ------------------------------------------------------------------
    # Venv creation
    # ------------------------------------------------------------------

    @staticmethod
    def _create_venv(dest: Path) -> None:
        if _have_uv():
            # `--seed` ensures pip is present in the venv so subsequent
            # editable installs work even if a step has to fall back.
            _run(["uv", "venv", "--seed", str(dest)])
        else:
            _run([sys.executable, "-m", "venv", str(dest)])

    @staticmethod
    def _install_packages(python: Path, manifest: AgentManifest) -> None:
        # Build the platform-runtime install spec, including framework extras.
        extras = FRAMEWORK_EXTRAS.get(manifest.framework)
        platform_src = _platform_source_dir()
        if extras:
            platform_spec = f"{platform_src}[{extras}]"
        else:
            platform_spec = str(platform_src)

        specs = ["-e", platform_spec, *manifest.requirements]

        if _have_uv():
            # `--python` points uv at the venv's interpreter so installs
            # land in the venv, not the host environment.
            _run(["uv", "pip", "install", "--python", str(python), *specs])
        else:
            _run([str(python), "-m", "pip", "install", *specs])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _have_uv() -> bool:
    return shutil.which("uv") is not None


def _python_in_venv(venv: Path) -> Path:
    if sys.platform == "win32":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def _platform_source_dir() -> Path:
    """Locate the directory containing platform-runtime's pyproject.toml.

    Walks up from `platform_runtime/__init__.py`. This works for both
    `pip install -e <repo>` (returns the repo root) and the source-layout
    we use in-repo today.
    """
    here = Path(__file__).resolve().parent
    for ancestor in (here, *here.parents):
        if (ancestor / "pyproject.toml").is_file():
            return ancestor
    raise VenvError(
        "Could not locate the platform-runtime source root "
        "(no pyproject.toml found in the ancestor chain)."
    )


def _run(cmd: list[str]) -> None:
    """Run a subprocess synchronously, capture output, raise on non-zero."""
    logger.debug("$ %s", " ".join(cmd))
    subprocess.run(cmd, check=True, capture_output=True)
