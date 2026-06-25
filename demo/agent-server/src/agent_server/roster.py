"""The agent roster + per-agent ``ui.yaml`` loading.

The roster is the ``GET /agents`` payload: one entry per agent with the
fields the HexKit proxy/shell needs to render a picker and theme the chrome.
``main_color`` is the single color that drives the active agent's accent.
"""

from __future__ import annotations

from pathlib import Path

_AGENTS_DIR = Path(__file__).parent / "agents"

# Each agent co-locates its UI config with its sources (one folder per agent).
_UI_PATHS = {
    "devops": _AGENTS_DIR / "tech_org" / "devops" / "ui.yaml",
    "itsm": _AGENTS_DIR / "tech_org" / "itsm" / "ui.yaml",
    "healthcare": _AGENTS_DIR / "clinic_org" / "healthcare" / "ui.yaml",
    "hr": _AGENTS_DIR / "shared" / "hr" / "ui.yaml",
}

# id -> public roster entry. ``ui_url`` is relative to the agent-server root;
# the proxy rewrites/serves it under its own /agents/{id}/ui. ``framework`` tells
# the proxy which translator to apply to this agent's native event stream
# (`native` is the escape hatch). Each entry is a real agent; HexGate wrapping is
# opt-in (enabled by setting HEXGATE_KEY).
AGENTS: list[dict[str, str]] = [
    # Healthcare — a real OpenAI Agents SDK agent; HexGate wrapping is opt-in
    # (enabled by setting HEXGATE_KEY).
    {
        "id": "healthcare",
        "name": "Healthcare",
        "role": "Clinical assistant",
        "main_color": "#0ea5b7",
        "ui_url": "/agents/healthcare/ui",
        "framework": "openai-agents",
    },
    # DevOps — a real Google ADK agent (LiteLLM over an OpenAI model); HexGate
    # wrapping is opt-in (enabled by setting HEXGATE_KEY).
    {
        "id": "devops",
        "name": "DevOps",
        "role": "Infra assistant",
        "main_color": "#8b5cf6",
        "ui_url": "/agents/devops/ui",
        "framework": "google-adk",
    },
    # ITSM — a real deepagents/LangChain agent; HexGate wrapping is opt-in
    # (enabled by setting HEXGATE_KEY). The real-LLM showcase for the LangChain
    # translator (RBAC + state-machine guard on a Change-Request workflow).
    {
        "id": "itsm",
        "name": "ITSM",
        "role": "Change-request assistant",
        "main_color": "#d97706",
        "ui_url": "/agents/itsm/ui",
        "framework": "langchain",
    },
    # HR — a real LangChain agent (create_react_agent); HexGate wrapping is opt-in
    # (enabled by setting HEXGATE_KEY). Showcases role-based field-level scoping
    # over an employee record (default < manager < gestionnaire_rh).
    {
        "id": "hr",
        "name": "HR",
        "role": "People assistant",
        "main_color": "#0d9488",
        "ui_url": "/agents/hr/ui",
        "framework": "langchain",
    },
]

_BY_ID = {a["id"]: a for a in AGENTS}


def get_agent(agent_id: str) -> dict[str, str] | None:
    return _BY_ID.get(agent_id)


def read_ui(agent_id: str) -> str | None:
    """Return the agent's ``ui.yaml`` text, or ``None`` when absent."""
    path = _UI_PATHS.get(agent_id)
    if path is None or not path.is_file():
        return None
    return path.read_text(encoding="utf-8")
