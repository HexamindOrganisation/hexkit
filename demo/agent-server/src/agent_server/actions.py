"""Reference widget actions (CONTRACT.md §5b) for the Orbit research workspace.

Backs the `data_source` + `action` + `refresh` mechanism: an action returns a
single `{result}` and never pushes to the UI; display widgets re-pull their
`data_source` when an action names them in `refresh` (declared in the ui.yaml).

State is process-global and in-memory — fine for the single-user demo. A real
backend would persist per-user / per-conversation.
"""

from __future__ import annotations

import csv
import io
from typing import Any

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


_ACTIONS = {
    "list_sources": _list_sources,
    "seed_sources": _seed_sources,
    "clear_sources": _clear_sources,
}


def run_action(name: str, args: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the action's result, or `None` when the name is unknown."""
    handler = _ACTIONS.get(name)
    return handler(args or {}) if handler else None
