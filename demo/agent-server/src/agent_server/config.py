"""Process configuration, read from ``AGENT_*`` environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8880


def get_settings() -> Settings:
    return Settings(
        host=os.getenv("AGENT_HOST", "127.0.0.1"),
        port=int(os.getenv("AGENT_PORT", "8880")),
    )
