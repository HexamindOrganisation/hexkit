"""Reference widget actions (CONTRACT.md §5b) for the Orbit + DevOps workspaces.

Backs the `data_source` + `action` + `refresh` mechanism: an action returns a
single `{result}` and never pushes to the UI; display widgets re-pull their
`data_source` when an action names them in `refresh` (declared in the ui.yaml).
Action names are globally unique, so one flat registry serves every agent.

State is process-global and in-memory — fine for the single-user demo. A real
backend would persist per-user / per-conversation.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from .agents import devops_state, itsm_db

# The "retrieved sources" the Orbit `sources` table displays.
_SOURCES: list[dict[str, Any]] = []

_SEED: list[dict[str, Any]] = [
    {"title": "Retrieval-augmented generation: a survey", "url": "https://example.com/rag-survey", "score": 0.94},
    {"title": "Vector index benchmarks (2026)", "url": "https://example.com/vector-bench", "score": 0.91},
    {"title": "Chunking strategies that actually matter", "url": "https://example.com/chunking", "score": 0.88},
    {"title": "Evaluating grounded answers", "url": "https://example.com/grounded-eval", "score": 0.83},
    {"title": "Hybrid search: BM25 + embeddings", "url": "https://example.com/hybrid-search", "score": 0.79},
]


def _sources_csv() -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Title", "URL", "Score"])
    for s in _SOURCES:
        writer.writerow([s["title"], s["url"], s["score"]])
    return buf.getvalue()


def _list_sources(_args: dict[str, Any]) -> dict[str, Any]:
    """Data source for the `sources` table — return the rows as CSV."""
    return {"csv": _sources_csv()}


def _seed_sources(_args: dict[str, Any]) -> dict[str, Any]:
    """Side-effect: populate a sample result set (a fake 'search')."""
    _SOURCES.clear()
    _SOURCES.extend(_SEED)
    return {"count": len(_SOURCES)}


def _clear_sources(_args: dict[str, Any]) -> dict[str, Any]:
    """Side-effect: drop all sources."""
    removed = len(_SOURCES)
    _SOURCES.clear()
    return {"removed": removed}


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
    # Orbit research workspace
    "list_sources": _list_sources,
    "seed_sources": _seed_sources,
    "clear_sources": _clear_sources,
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
