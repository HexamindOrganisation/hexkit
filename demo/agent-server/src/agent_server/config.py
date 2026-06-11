"""Process configuration, read from ``AGENT_*`` environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 9080
    # Default OFF — the reference path is the deterministic echo agent so the
    # contract is testable without a real provider key. Set AGENT_ENABLE_LLM=1
    # to route to the optional OpenAI-backed agent when a key is forwarded.
    enable_llm: bool = False


def get_settings() -> Settings:
    return Settings(
        host=os.getenv("AGENT_HOST", "127.0.0.1"),
        port=int(os.getenv("AGENT_PORT", "9080")),
        enable_llm=os.getenv("AGENT_ENABLE_LLM", "0") == "1",
    )
