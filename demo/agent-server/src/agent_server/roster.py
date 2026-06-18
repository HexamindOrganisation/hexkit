"""The agent roster + per-agent ``ui.yaml`` loading.

The roster is the ``GET /agents`` payload: one entry per agent with the
fields the HexaUI proxy/shell needs to render a picker and theme the chrome.
``main_color`` is the single color that drives the active agent's accent.
"""

from __future__ import annotations

from pathlib import Path

_UI_DIR = Path(__file__).parent / "ui"

# id -> public roster entry. ``ui_url`` is relative to the agent-server root;
# the proxy rewrites/serves it under its own /agents/{id}/ui. ``framework`` tells
# the proxy which translator to apply to this agent's native event stream — each
# reference agent demonstrates one framework path (`native` is the escape hatch).
#   - Probe (native): the simple real-LLM chat showcase (OpenAI).
#   - Orbit (google-adk): the "complex" showcase — a real LLM via Google ADK /
#     Gemini PLUS a widget actions + data-source workspace (see ui/orbit.yaml).
# Both stream a real model when AGENT_ENABLE_LLM is set and the matching key is
# forwarded; otherwise they fall back (echo / canned ADK events).
AGENTS: list[dict[str, str]] = [
    {
        "id": "probe",
        "name": "Probe",
        "role": "General assistant",
        "main_color": "#3f9d94",
        "ui_url": "/agents/probe/ui",
        "framework": "native",
    },
    {
        "id": "atlas",
        "name": "Atlas",
        "role": "Operations copilot",
        "main_color": "#4f74c9",
        "ui_url": "/agents/atlas/ui",
        "framework": "langchain",
    },
    {
        "id": "forge",
        "name": "Forge",
        "role": "Code & build",
        "main_color": "#56809e",
        "ui_url": "/agents/forge/ui",
        "framework": "openai-agents",
    },
    {
        "id": "orbit",
        "name": "Orbit",
        "role": "Research workspace",
        "main_color": "#b0714f",
        "ui_url": "/agents/orbit/ui",
        "framework": "google-adk",
    },
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
]

_BY_ID = {a["id"]: a for a in AGENTS}


def get_agent(agent_id: str) -> dict[str, str] | None:
    return _BY_ID.get(agent_id)


def read_ui(agent_id: str) -> str | None:
    """Return the agent's ``ui.yaml`` text, or ``None`` when absent."""
    path = _UI_DIR / f"{agent_id}.yaml"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")
