"""
Per-agent UI-triggered actions.

Convention
----------
- An agent ships an `actions.py` next to its `agent.yaml`.
- The manifest's `actions:` field lists which functions are exposed.
- Each function takes `(args, *, context)` and returns a JSON-able value.
- The function may emit side-effect "widget update" events via
  `context.emit(widget, payload)`. Those events are returned alongside
  the action's result and the front-end re-emits them through the
  bridge so the matching widget's inbox receives them.

The actions surface is deliberately separate from the `UnifiedAgentRuntime`
protocol. Agents talk to models via the runtime; UIs talk to action
handlers via this module. They share a process (and a worker, in
subprocess isolation) but no abstraction.
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

from pydantic import BaseModel, Field

from .manifest import AgentManifest

if TYPE_CHECKING:
    from .subprocess_supervisor import WorkerSupervisor


logger = logging.getLogger("platform_runtime.actions")


# ---------------------------------------------------------------------------
# Wire types
# ---------------------------------------------------------------------------

class WidgetEvent(BaseModel):
    """One widget-targeted side-effect event emitted by an action handler.

    The front-end re-emits this as a `tool-call` AgentEvent so the lib's
    existing inbox machinery routes the payload to `useAgentInbox` on
    the widget named `widget`.
    """

    widget: str
    payload: Any = None


class ActionResult(BaseModel):
    """Envelope returned by every action invocation.

    `result` goes back to the caller of `dispatcher.invoke()`. `events`
    are fanned out to widgets by the bridge — never seen by the original
    caller.
    """

    result: Any = None
    events: list[WidgetEvent] = Field(default_factory=list)


class ActionError(Exception):
    """Raised for action lookup, validation, or handler failures."""


# ---------------------------------------------------------------------------
# Handler-side API
# ---------------------------------------------------------------------------

class ActionContext:
    """Object passed as `context=` to each action handler.

    Holds the side-effect events the handler emits during its run. We
    keep this minimal on purpose — future fields (tenant, user, secrets
    handle, run_id) extend the same object so existing handlers keep
    working unchanged.
    """

    def __init__(self) -> None:
        self.events: list[WidgetEvent] = []

    def emit(self, widget: str, payload: Any = None) -> None:
        """Queue a widget-targeted update. Delivered after the handler returns."""
        self.events.append(WidgetEvent(widget=widget, payload=payload))


# ---------------------------------------------------------------------------
# Host interface — one for in-process, one for subprocess proxy
# ---------------------------------------------------------------------------

class ActionHost(ABC):
    """Per-agent action dispatcher. Lifecycle parallels `UnifiedAgentRuntime`."""

    @property
    @abstractmethod
    def declared(self) -> list[str]:
        """Names declared in the manifest. Used by `/metadata` for the UI."""

    @abstractmethod
    async def invoke(self, name: str, args: dict[str, Any]) -> ActionResult:
        """Execute the named action with `args`, return its envelope."""

    async def aclose(self) -> None:
        return None


class LocalActionHost(ActionHost):
    """In-process action dispatch — callables live in this Python interpreter."""

    def __init__(
        self,
        declared: list[str],
        callables: dict[str, Callable[..., Any]],
    ) -> None:
        self._declared = list(declared)
        self._callables = dict(callables)

    @property
    def declared(self) -> list[str]:
        return list(self._declared)

    async def invoke(self, name: str, args: dict[str, Any]) -> ActionResult:
        if name not in self._declared:
            raise ActionError(f"Unknown action: {name!r}")
        fn = self._callables.get(name)
        if fn is None:
            raise ActionError(
                f"Action {name!r} declared but not loaded — "
                "module returned no such attribute"
            )

        ctx = ActionContext()
        try:
            value = fn(args, context=ctx)
            if inspect.isawaitable(value):
                value = await value
        except Exception as e:
            logger.exception("Action %r failed", name)
            raise ActionError(f"Action {name!r} raised: {e}") from e

        return ActionResult(result=value, events=ctx.events)


class RemoteActionHost(ActionHost):
    """Subprocess-mode dispatch — forwards to a worker via the IPC supervisor."""

    def __init__(
        self,
        declared: list[str],
        supervisor: "WorkerSupervisor",
    ) -> None:
        self._declared = list(declared)
        self._sup = supervisor

    @property
    def declared(self) -> list[str]:
        return list(self._declared)

    async def invoke(self, name: str, args: dict[str, Any]) -> ActionResult:
        if name not in self._declared:
            raise ActionError(f"Unknown action: {name!r}")
        raw = await self._sup.rpc("action", {"name": name, "args": args})
        return ActionResult.model_validate(raw)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

ACTIONS_FILENAME = "actions.py"


def load_action_callables(
    manifest: AgentManifest, root: Path
) -> dict[str, Callable[..., Any]]:
    """Import the agent's `actions.py` and return the callables it declares.

    Mirrors `AgentRegistry._resolve_callable` for the agent entrypoint:
    namespaces the synthetic module name with `agent_id` so two agents'
    `actions.py` files don't collide in `sys.modules`.

    Returns an empty dict when the manifest declares no actions — the
    file is not required to exist in that case. If actions ARE declared,
    a missing file or a missing function is a hard error.
    """
    if not manifest.actions:
        return {}

    actions_path = root / ACTIONS_FILENAME
    if not actions_path.is_file():
        raise ActionError(
            f"Manifest declares actions {manifest.actions} but "
            f"{actions_path} does not exist."
        )

    module_name = f"_platform_actions_{manifest.agent_id}"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    spec = importlib.util.spec_from_file_location(module_name, actions_path)
    if spec is None or spec.loader is None:
        raise ActionError(f"Could not build import spec for {actions_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        sys.modules.pop(module_name, None)
        raise ActionError(
            f"Importing {actions_path} failed: {e}"
        ) from e

    callables: dict[str, Callable[..., Any]] = {}
    for name in manifest.actions:
        fn = getattr(module, name, None)
        if fn is None:
            raise ActionError(
                f"Action {name!r} declared in manifest but not defined "
                f"in {actions_path}"
            )
        if not callable(fn):
            raise ActionError(
                f"{name!r} in {actions_path} is not callable"
            )
        callables[name] = fn
    return callables
