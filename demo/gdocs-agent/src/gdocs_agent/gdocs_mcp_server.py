"""Fake Google Docs MCP server — the third-party tool surface this agent gates.

A self-contained fixture (mirrors asianf/deploy/gates-demo/gdocs_mcp_server.py)
so this backend runs without the hexgate SDK repo checked out beside it. The
backend spawns it over stdio; the *policy* that gates it lives on the hexgate
platform (see this folder's README), not here.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

server = FastMCP("gdocs")

_DOCS = {
    "DOC-101": {"title": "Q3 launch plan", "body": "Ship the gate on the 14th."},
    "DOC-102": {"title": "Onboarding checklist", "body": "Laptop, badge, VPN."},
    "CONF-900": {"title": "Acquisition terms", "body": "Project Falcon — $42M."},
}


@server.tool(description="Search docs by a keyword in the title. Read-only.")
def search_docs(query: str) -> str:
    hits = [
        f"{doc_id}: {d['title']}"
        for doc_id, d in _DOCS.items()
        if query.lower() in d["title"].lower()
    ]
    return "\n".join(hits) if hits else f"no docs match {query!r}"


@server.tool(description="Read a document's full body by id.")
def read_doc(doc_id: str) -> str:
    doc = _DOCS.get(doc_id)
    return f"{doc['title']}\n\n{doc['body']}" if doc else f"no such doc: {doc_id}"


@server.tool(description="Create a new doc in a folder. Returns the new id.")
def create_doc(title: str, folder: str = "Drafts") -> str:
    return f"created '{title}' in {folder} — id=DOC-{len(_DOCS) + 100}"


@server.tool(description="Share a doc with recipients at a given role (viewer/editor/owner).")
def share_doc(doc_id: str, recipients: list[str], role: str = "viewer") -> str:
    return f"shared {doc_id} with {len(recipients)} recipient(s) as {role}"


@server.tool(description="Export a doc by POSTing it to an external URL.")
def export_doc(doc_id: str, url: str) -> str:
    return f"exported {doc_id} to {url}"


@server.tool(description="Permanently delete a doc. Destructive — needs confirm=true.")
def delete_doc(doc_id: str, confirm: bool = False) -> str:
    return f"deleted {doc_id}" if confirm else f"refused: pass confirm=true to delete {doc_id}"


if __name__ == "__main__":
    server.run("stdio")
