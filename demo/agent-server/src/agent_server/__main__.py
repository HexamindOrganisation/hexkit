"""Console entrypoint: ``python -m agent_server``."""

from __future__ import annotations

import uvicorn

from .config import get_settings
from .server.app import create_app

app = create_app()


def main() -> None:
    s = get_settings()
    uvicorn.run(app, host=s.host, port=s.port)


if __name__ == "__main__":
    main()
