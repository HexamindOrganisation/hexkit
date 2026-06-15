from pathlib import Path

_UI_DIR = Path(__file__).parent.parent / "ui"

AGENTS : list[dict[str, str]] = [
    {
        "id": "testagent",
        "name": "Test Agent",
        "role": "A test agent for demonstration purposes",
        "main_color": "#6366f1",
        "ui_url": "/agents/testagent/ui",
        "framework": "custom",
    },
]

_BY_ID = {agent["id"]: agent for agent in AGENTS}