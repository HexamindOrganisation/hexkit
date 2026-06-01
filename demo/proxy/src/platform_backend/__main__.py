"""Production entrypoint: `python -m platform_backend`.

Configuration is env-driven (`PLATFORM_*` — see `config.py`). The lifespan
hook in `server.app.create_app` owns the database engine.
"""

from __future__ import annotations

import logging

import uvicorn

from .config import get_settings
from .server import create_app


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    app = create_app()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
