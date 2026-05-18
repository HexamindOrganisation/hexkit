"""
Agent manifest: the `agent.yaml` file each wrapped agent ships.

The manifest is the contract between an agent author and the platform. It
declares which framework the agent uses, how to find its entrypoint, what
capabilities it claims, and any runtime requirements. The platform reads it
to decide which adapter to instantiate and to populate `AgentMetadata`.

This module does ONE thing: parse + validate manifest files. It does not
import the agent's code; that is the registry's job. Keeping these concerns
separated means we can lint / list / serve manifests without ever executing
agent code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from .protocol import AgentCapabilities


MANIFEST_FILENAME = "agent.yaml"


# Frameworks the platform knows how to wrap. Adding a new adapter means
# adding a member here and registering it in the adapter registry.
SUPPORTED_FRAMEWORKS = frozenset({"langchain", "openai-agents"})


class AgentManifest(BaseModel):
    """Parsed and validated `agent.yaml`.

    Path fields (`entrypoint`) are stored as POSIX-style strings as written
    in the YAML; resolution against the manifest directory happens via
    `resolved_entrypoint(root)`.
    """

    agent_id: str
    name: str
    framework: str
    entrypoint: str
    agent_callable: str
    version: str = "0.0.0"
    description: str = ""
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    requirements: list[str] = Field(default_factory=list)
    env: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    @field_validator("framework")
    @classmethod
    def _known_framework(cls, v: str) -> str:
        if v not in SUPPORTED_FRAMEWORKS:
            raise ValueError(
                f"framework '{v}' is not supported. "
                f"Known: {sorted(SUPPORTED_FRAMEWORKS)}"
            )
        return v

    @field_validator("agent_id")
    @classmethod
    def _valid_agent_id(cls, v: str) -> str:
        if not v or not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError(
                "agent_id must be non-empty and contain only "
                "alphanumerics, dash, or underscore"
            )
        return v

    def resolved_entrypoint(self, root: Path) -> Path:
        """Absolute path to the entrypoint Python file, given the manifest dir."""
        return (root / self.entrypoint).resolve()


class ManifestError(Exception):
    """Raised for any failure to locate, parse, or validate a manifest."""


def load_manifest(agent_dir: Path | str) -> tuple[AgentManifest, Path]:
    """Load `agent.yaml` from a directory.

    Returns
    -------
    (manifest, agent_root)
        `manifest`   — validated `AgentManifest`
        `agent_root` — absolute path to the directory containing the manifest,
                       used later to resolve relative paths and to set up
                       `sys.path` when importing the entrypoint.
    """
    root = Path(agent_dir).resolve()
    if not root.is_dir():
        raise ManifestError(f"Agent directory not found: {root}")

    manifest_path = root / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise ManifestError(
            f"No {MANIFEST_FILENAME} found in {root}"
        )

    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ManifestError(f"Invalid YAML in {manifest_path}: {e}") from e

    if not isinstance(raw, dict):
        raise ManifestError(
            f"{manifest_path} must contain a YAML mapping at the top level"
        )

    try:
        manifest = AgentManifest.model_validate(raw)
    except ValidationError as e:
        raise ManifestError(
            f"Manifest validation failed for {manifest_path}:\n{e}"
        ) from e

    entrypoint_path = manifest.resolved_entrypoint(root)
    if not entrypoint_path.is_file():
        raise ManifestError(
            f"Entrypoint '{manifest.entrypoint}' not found "
            f"(resolved to {entrypoint_path})"
        )

    return manifest, root
