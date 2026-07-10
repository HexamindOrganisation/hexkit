"""Console entrypoint: ``python -m gdocs_agent``.

Defaults to :8880 — the port the HexKit proxy proxies by default
(``PLATFORM_AGENT_BACKEND_URL``), so this backend can stand in as the demo's
only agent server with no proxy config. Override with AGENT_HOST / AGENT_PORT.
"""

from __future__ import annotations

import os

import uvicorn

from .app import create_app

app = create_app()


def main() -> None:
    host = os.getenv("AGENT_HOST", "127.0.0.1")
    port = int(os.getenv("AGENT_PORT", "8880"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
