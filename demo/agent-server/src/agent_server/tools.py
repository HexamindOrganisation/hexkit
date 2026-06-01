"""A couple of canned fake tools, so the reference stream exercises the
tool-call events without depending on anything external."""

from __future__ import annotations

from typing import Any


def fake_search(query: str) -> dict[str, Any]:
    """Return a canned search result set for ``query``."""
    q = query or "your query"
    return {
        "query": q,
        "results": [
            {
                "title": f"Result for '{q}'",
                "url": "https://example.com/a",
                "snippet": "A canned snippet returned by the reference agent.",
            },
            {
                "title": "Background reading",
                "url": "https://example.com/b",
                "snippet": "Another canned snippet.",
            },
        ],
    }


def fake_fetch(url: str) -> dict[str, Any]:
    """Return canned page content for ``url``."""
    return {
        "url": url,
        "title": "Fetched page",
        "content": f"Canned body for {url}.",
    }
