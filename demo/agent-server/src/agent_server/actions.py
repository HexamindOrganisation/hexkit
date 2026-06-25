"""Reference widget actions (CONTRACT.md §5b) for the DevOps + ITSM workspaces.

Backs the `data_source` + `action` + `refresh` mechanism: an action returns a
single `{result}` and never pushes to the UI; display widgets re-pull their
`data_source` when an action names them in `refresh` (declared in the ui.yaml).
Action names are globally unique, so one flat registry serves every agent.

State is process-global and in-memory — fine for the single-user demo. A real
backend would persist per-user / per-conversation.
"""

from __future__ import annotations

from typing import Any

from .agents.tech_org.devops import devops_state
from .agents.tech_org.itsm import itsm_db

# ── DevOps service-state panel (CONTRACT §5b) ────────────────────────────────
# The env buttons call `select_env`; the two display widgets pull `service_summary`
# (metrics) and `service_state` (table) for the selected env. The agent's tools
# mutate the same `devops_state`, so the panel shows the impact of a run.


def _select_env(args: dict[str, Any]) -> dict[str, Any]:
    devops_state.select_env(args.get("env", "dev"))
    return {"env": devops_state.selected_env()}


def _service_summary(_args: dict[str, Any]) -> dict[str, Any]:
    return devops_state.summary(devops_state.selected_env())


def _service_state(_args: dict[str, Any]) -> dict[str, Any]:
    return {"csv": devops_state.table_csv(devops_state.selected_env())}


# ── ITSM lifecycle board (CONTRACT §5b) ──────────────────────────────────────
# The Refresh button calls `refresh_changes`; the metrics show the per-state
# funnel and the table lists every change. The agent's tools mutate the same
# `itsm_db`, so a Refresh shows the impact of a run. Global view — no per-user
# scope (unlike the chat tools).


def _refresh_changes(_args: dict[str, Any]) -> dict[str, Any]:
    """No-op trigger for the Refresh button — the metrics + table re-pull."""
    return itsm_db.state_counts()


def _change_summary(_args: dict[str, Any]) -> dict[str, Any]:
    return itsm_db.state_counts()


def _change_table(_args: dict[str, Any]) -> dict[str, Any]:
    return {"csv": itsm_db.board_csv()}


_ACTIONS = {
    # DevOps service-state panel
    "select_env": _select_env,
    "service_summary": _service_summary,
    "service_state": _service_state,
    # ITSM lifecycle board
    "refresh_changes": _refresh_changes,
    "change_summary": _change_summary,
    "change_table": _change_table,
}


def run_action(name: str, args: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the action's result, or `None` when the name is unknown."""
    handler = _ACTIONS.get(name)
    return handler(args or {}) if handler else None
