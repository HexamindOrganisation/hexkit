"""
Production entrypoint: `python -m platform_runtime`.

Reads configuration from environment variables:

    PLATFORM_AGENTS_DIR   directory to scan for `agent.yaml` files (required)
    PLATFORM_ISOLATION    'in_process' (default) | 'subprocess'
    PLATFORM_HOST         bind host (default: 127.0.0.1)
    PLATFORM_PORT         bind port (default: 8080)
    PLATFORM_LOG_LEVEL    uvicorn log level (default: info)

Importing the adapters here is what activates them: the `@register_adapter`
decorator only fires once the adapter module is imported. New adapters get
one more import line here. In SUBPROCESS isolation mode the adapter imports
happen inside each worker process instead — but we still import them here
so manifests can be validated up front against the same `SUPPORTED_FRAMEWORKS`
set.
"""

from __future__ import annotations

import logging
import os
import sys

import uvicorn

from .adapters import langchain_adapter  # noqa: F401
from .registry import AgentRegistry, IsolationMode
from .server import create_app


def main() -> None:
    agents_dir = os.environ.get("PLATFORM_AGENTS_DIR")
    if not agents_dir:
        sys.stderr.write(
            "PLATFORM_AGENTS_DIR is required (path to a directory "
            "containing agent folders with agent.yaml manifests).\n"
        )
        sys.exit(2)

    isolation_raw = os.environ.get("PLATFORM_ISOLATION", "in_process").lower()
    try:
        isolation = IsolationMode(isolation_raw)
    except ValueError:
        sys.stderr.write(
            f"PLATFORM_ISOLATION must be one of "
            f"{[m.value for m in IsolationMode]}, got '{isolation_raw}'.\n"
        )
        sys.exit(2)

    log_level = os.environ.get("PLATFORM_LOG_LEVEL", "info")
    logging.basicConfig(level=log_level.upper())

    registry = AgentRegistry(isolation=isolation)
    loaded = registry.discover(agents_dir)
    logging.getLogger("platform_runtime").info(
        "Loaded %d agent(s) in %s mode: %s",
        len(loaded),
        isolation.value,
        [a.manifest.agent_id for a in loaded],
    )

    app = create_app(registry)
    uvicorn.run(
        app,
        host=os.environ.get("PLATFORM_HOST", "127.0.0.1"),
        port=int(os.environ.get("PLATFORM_PORT", "8080")),
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
