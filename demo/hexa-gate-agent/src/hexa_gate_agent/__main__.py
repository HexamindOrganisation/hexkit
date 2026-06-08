"""Console entrypoint: ``python -m hexa_gate_agent`` (serves on :8080)."""

from __future__ import annotations

import os

import uvicorn

from .app import create_app

app = create_app()


def main() -> None:
    host = os.getenv("AGENT_HOST", "127.0.0.1")
    port = int(os.getenv("AGENT_PORT", "8080"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
