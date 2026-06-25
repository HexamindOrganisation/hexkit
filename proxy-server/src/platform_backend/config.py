"""
Environment-driven settings for the platform backend.

Mirrors `platform_runtime.__main__`'s `PLATFORM_*` env-var contract so both
services configure the same way. Settings are loaded once at startup; reach
them via `get_settings()` (lru-cached, FastAPI-injectable).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PLATFORM_", extra="ignore")

    database_url: str = Field(
        default="sqlite+aiosqlite:///./hexa.sqlite",
        description=(
            "Async SQLAlchemy URL for the primary database. Defaults to a local "
            "SQLite file — no server to deploy. For multi-worker / high-concurrency "
            "deployments, install the `postgres` extra and set a "
            "`postgresql+asyncpg://…` URL."
        ),
    )
    jwt_secret: str = Field(
        default="dev-only-change-me-dev-only-change-me",
        description="HS256 signing secret. Override in production (>=32 bytes).",
    )
    jwt_expiry_seconds: int = 60 * 60 * 24  # 24h
    agent_backend_url: str = Field(
        default="http://127.0.0.1:8880",
        description="Base URL of the developer's agent backend to proxy "
        "(env PLATFORM_AGENT_BACKEND_URL).",
    )
    host: str = "127.0.0.1"
    port: int = 8800
    log_level: str = "info"
    demo_users_file: str = Field(
        default="",
        description=(
            "Path to a YAML file describing demo accounts to upsert on "
            "startup (see `auth/demo_users.py`). Empty = no seeding. "
            "Env: PLATFORM_DEMO_USERS_FILE."
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
