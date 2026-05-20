"""
Agent registry: discover folders, load manifests, import entrypoints,
instantiate adapters, and serve the resulting `UnifiedAgentRuntime` instances
by `agent_id`.

This is the only place in the codebase that imports agent code. Everything
downstream (server, CLI) interacts with already-instantiated runtimes.

Lifecycle
---------
1. `discover(root)` walks `root` looking for `agent.yaml` files.
2. For each, `load(agent_dir)` is called:
   - parses the manifest
   - puts the agent dir on `sys.path` so the entrypoint can import siblings
   - imports the entrypoint by file path under a unique module name
   - resolves `agent_callable` inside the imported module
   - looks up the adapter class for the declared framework
   - constructs the adapter and stores it by `agent_id`
3. `get(agent_id)` returns the runtime instance.
4. `aclose()` closes every runtime on shutdown.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

from .actions import (
    ActionError,
    ActionHost,
    LocalActionHost,
    RemoteActionHost,
    load_action_callables,
)
from .adapters import get_adapter_class
from .adapters.remote_adapter import RemoteAdapter
from .manifest import MANIFEST_FILENAME, AgentManifest, ManifestError, load_manifest
from .protocol import UnifiedAgentRuntime
from .subprocess_supervisor import WorkerSupervisor
from .venv_manager import VenvManager


logger = logging.getLogger("platform_runtime.registry")


class IsolationMode(str, Enum):
    """How agents are hosted relative to the server process.

    - IN_PROCESS:  the agent's code is imported directly into the server.
                   Lowest overhead, no isolation.
    - SUBPROCESS:  each agent runs in its own `python -m platform_runtime.worker`
                   child process. The server never imports agent code.
    """

    IN_PROCESS = "in_process"
    SUBPROCESS = "subprocess"


class RegistryError(Exception):
    """Raised for any failure while loading or resolving an agent."""


@dataclass
class LoadedAgent:
    """One fully-loaded agent, ready to serve."""

    manifest: AgentManifest
    root: Path
    runtime: UnifiedAgentRuntime
    # `None` when the manifest declares no actions. In-process mode holds
    # a `LocalActionHost`; subprocess mode holds a `RemoteActionHost` that
    # forwards over the same supervisor the runtime uses.
    actions: ActionHost | None = None


class AgentRegistry:
    """In-memory map of `agent_id` → `LoadedAgent`."""

    def __init__(
        self,
        isolation: IsolationMode = IsolationMode.IN_PROCESS,
        *,
        python_executable: str | None = None,
        venv_manager: VenvManager | None = None,
    ) -> None:
        self._agents: dict[str, LoadedAgent] = {}
        self._isolation = isolation
        # Interpreter to use as a fallback when a manifest has no
        # requirements. None ⇒ inherit the parent's `sys.executable`.
        self._python_executable = python_executable
        # When an agent declares `requirements:`, the venv manager
        # materializes a per-agent venv whose python overrides the fallback.
        # Disabled by passing `venv_manager=False` (we accept that as None,
        # see below) — but defaulting it on in subprocess mode is what
        # makes `requirements:` Just Work.
        if venv_manager is None and isolation is IsolationMode.SUBPROCESS:
            venv_manager = VenvManager()
        self._venv_manager: VenvManager | None = venv_manager

    @property
    def isolation(self) -> IsolationMode:
        return self._isolation

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self, root: Path | str) -> list[LoadedAgent]:
        """Walk `root` and load every agent whose folder contains `agent.yaml`.

        Errors loading a single agent are wrapped in `RegistryError` with a
        path prefix so a partial-failure scenario is easy to diagnose. We
        deliberately do NOT swallow them — discovery is a startup step and
        a broken manifest should block startup, not produce a half-loaded
        platform.
        """
        root = Path(root).resolve()
        if not root.is_dir():
            raise RegistryError(f"Discovery root not found: {root}")

        loaded: list[LoadedAgent] = []
        for manifest_path in sorted(root.rglob(MANIFEST_FILENAME)):
            try:
                loaded.append(self.load(manifest_path.parent))
            except (ManifestError, RegistryError) as e:
                raise RegistryError(
                    f"Failed to load agent at {manifest_path.parent}: {e}"
                ) from e
        return loaded

    # ------------------------------------------------------------------
    # Single-agent load
    # ------------------------------------------------------------------

    def load(self, agent_dir: Path | str) -> LoadedAgent:
        manifest, root = load_manifest(agent_dir)

        if manifest.agent_id in self._agents:
            raise RegistryError(
                f"Duplicate agent_id '{manifest.agent_id}' "
                f"(already loaded from {self._agents[manifest.agent_id].root})"
            )

        if self._isolation is IsolationMode.IN_PROCESS:
            runtime = self._build_in_process(manifest, root)
            actions = self._build_local_actions(manifest, root)
        elif self._isolation is IsolationMode.SUBPROCESS:
            runtime = self._build_subprocess(manifest, root)
            actions = self._build_remote_actions(manifest, runtime)
        else:
            raise RegistryError(f"Unknown isolation mode: {self._isolation}")

        loaded = LoadedAgent(
            manifest=manifest, root=root, runtime=runtime, actions=actions
        )
        self._agents[manifest.agent_id] = loaded
        return loaded

    @staticmethod
    def _build_local_actions(
        manifest: AgentManifest, root: Path
    ) -> ActionHost | None:
        if not manifest.actions:
            return None
        try:
            callables = load_action_callables(manifest, root)
        except ActionError as e:
            raise RegistryError(str(e)) from e
        return LocalActionHost(declared=manifest.actions, callables=callables)

    @staticmethod
    def _build_remote_actions(
        manifest: AgentManifest, runtime: UnifiedAgentRuntime
    ) -> ActionHost | None:
        if not manifest.actions:
            return None
        # The runtime in subprocess mode is the RemoteAdapter; we reach
        # into its supervisor so action RPCs share the same wire and
        # lifecycle as runtime RPCs.
        sup = getattr(runtime, "_sup", None)
        if not isinstance(sup, WorkerSupervisor):
            raise RegistryError(
                "Subprocess mode expected a RemoteAdapter-backed runtime "
                "for action proxying."
            )
        return RemoteActionHost(declared=manifest.actions, supervisor=sup)

    def _build_in_process(
        self, manifest: AgentManifest, root: Path
    ) -> UnifiedAgentRuntime:
        """Construct an in-process adapter for `manifest.framework`."""
        factory = self._resolve_callable(manifest, root)
        adapter_cls = get_adapter_class(manifest.framework)
        try:
            return adapter_cls(manifest=manifest, root=root, factory=factory)
        except Exception as e:
            raise RegistryError(
                f"Adapter {adapter_cls.__name__} failed to initialize "
                f"for agent '{manifest.agent_id}': {e}"
            ) from e

    def _build_subprocess(
        self, manifest: AgentManifest, root: Path
    ) -> UnifiedAgentRuntime:
        """Construct a RemoteAdapter backed by an unstarted supervisor.

        The supervisor is NOT started here. Callers must invoke
        `await registry.start_all()` before serving. This keeps `load()`
        synchronous (so discovery stays straightforward) while preserving
        fail-fast behavior at the explicit warmup step.
        """
        # Pick the interpreter. Priority:
        #   1. per-agent venv (if manifest has requirements and a venv
        #      manager is configured),
        #   2. registry-level override (`python_executable=...`),
        #   3. parent's sys.executable (supervisor default).
        python = self._python_executable
        if self._venv_manager is not None:
            venv_python = self._venv_manager.ensure_venv(manifest, root)
            if venv_python is not None:
                python = str(venv_python)

        supervisor = WorkerSupervisor(str(root), python_executable=python)
        logger.info(
            "Prepared subprocess worker for agent_id=%s framework=%s "
            "(python=%s, not started)",
            manifest.agent_id,
            manifest.framework,
            python or "<sys.executable>",
        )
        return RemoteAdapter(supervisor=supervisor)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, agent_id: str) -> LoadedAgent:
        try:
            return self._agents[agent_id]
        except KeyError as e:
            raise RegistryError(f"Unknown agent_id: {agent_id}") from e

    def list(self) -> list[LoadedAgent]:
        return list(self._agents.values())

    def __contains__(self, agent_id: str) -> bool:
        return agent_id in self._agents

    def __iter__(self) -> Iterable[LoadedAgent]:
        return iter(self._agents.values())

    # ------------------------------------------------------------------
    # Async warmup
    # ------------------------------------------------------------------

    async def start_all(self) -> None:
        """Start any subprocess workers in parallel. No-op for in-process.

        Called from the server's lifespan after `discover()` so that a
        worker that fails to come up blocks server startup rather than
        manifesting as a 500 on the first request.
        """
        if self._isolation is not IsolationMode.SUBPROCESS:
            return

        starts: list[asyncio.Future] = []
        for loaded in self._agents.values():
            # Reach into the proxy for its supervisor. We could also expose
            # a `start()` on RemoteAdapter, but the adapter is supposed to
            # be transport-opaque; the registry is the right place to know
            # about supervisors.
            sup = getattr(loaded.runtime, "_sup", None)
            if isinstance(sup, WorkerSupervisor) and not sup.is_alive():
                starts.append(asyncio.create_task(sup.start()))

        if starts:
            # `gather` with return_exceptions=False so a single bad worker
            # surfaces immediately. Other supervisors that succeeded keep
            # their processes; aclose() in the lifespan finally-block will
            # tear them down.
            await asyncio.gather(*starts)
            logger.info("Started %d worker(s)", len(starts))

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        for loaded in self._agents.values():
            for closeable in (loaded.actions, loaded.runtime):
                if closeable is None:
                    continue
                try:
                    await closeable.aclose()
                except Exception:
                    # Best-effort shutdown; one bad component must not
                    # block teardown of the others.
                    pass
        self._agents.clear()

    # ------------------------------------------------------------------
    # Internal: import the entrypoint and resolve the callable
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_callable(manifest: AgentManifest, root: Path):
        """Import `manifest.entrypoint` and return `manifest.agent_callable`.

        Multi-file agents
        -----------------
        Two locations are prepended to `sys.path` to cover the common shapes
        of multi-file agent layouts:

        - The manifest directory (`root`). This makes manifest-rooted
          absolute imports work, e.g. `from app.tools import foo` when the
          agent dir is `<root>/app/...`.
        - The entrypoint's own directory. This mirrors the convention of
          running `python <script>` directly, where the script's folder is
          on `sys.path`. It allows `from tools import foo` when the
          entrypoint and `tools.py` sit side by side, no `__init__.py`
          required.

        The entrypoint file itself is loaded under a synthetic module name
        derived from the agent_id, so two agents with an `agent.py` next to
        their manifests do not collide in `sys.modules`.
        """
        entrypoint_path = manifest.resolved_entrypoint(root)
        module_name = f"_platform_agent_{manifest.agent_id}"

        # Order matters: insert(0) puts the entrypoint dir first so that an
        # agent's local file shadows any same-named package elsewhere on
        # sys.path. The manifest dir goes second.
        for path in (entrypoint_path.parent, root):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))

        spec = importlib.util.spec_from_file_location(module_name, entrypoint_path)
        if spec is None or spec.loader is None:
            raise RegistryError(
                f"Could not build import spec for {entrypoint_path}"
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            sys.modules.pop(module_name, None)
            raise RegistryError(
                f"Importing entrypoint {entrypoint_path} failed: {e}"
            ) from e

        try:
            factory = getattr(module, manifest.agent_callable)
        except AttributeError as e:
            raise RegistryError(
                f"Entrypoint {entrypoint_path} has no attribute "
                f"'{manifest.agent_callable}'"
            ) from e

        if not callable(factory):
            raise RegistryError(
                f"'{manifest.agent_callable}' in {entrypoint_path} is not callable"
            )

        return factory
