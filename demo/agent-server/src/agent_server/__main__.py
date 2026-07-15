"""Console entrypoint: ``python -m agent_server``."""

from __future__ import annotations

import logging
from pathlib import Path

import uvicorn

# Load secrets (OPENAI_API_KEY, GOOGLE_API_KEY, HEXGATE_API_KEY) from the
# agent-server .env. Real env vars take precedence.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")  # demo/agent-server/.env
except ImportError:
    pass

from .config import get_settings
from .server.app import create_app

app = create_app()


def main() -> None:
    s = get_settings()
    # uvicorn only configures its own loggers; add a root handler so the
    # agents' logging (e.g. the HexGate policy decisions) shows.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    uvicorn.run(app, host=s.host, port=s.port)


if __name__ == "__main__":
    main()
