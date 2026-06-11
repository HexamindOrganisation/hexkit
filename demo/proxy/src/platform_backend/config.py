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
        default="postgresql+asyncpg://platform:platform@127.0.0.1:5432/platform",
        description="Async SQLAlchemy URL for the primary database.",
    )
    jwt_secret: str = Field(
        default="dev-only-change-me-dev-only-change-me",
        description="HS256 signing secret. Override in production (>=32 bytes).",
    )
    jwt_expiry_seconds: int = 60 * 60 * 24  # 24h
    fernet_key: str = Field(
        default="",
        description=(
            "Url-safe-base64 32-byte key used to encrypt per-user API keys. "
            "Generate with `Fernet.generate_key()`. Empty in dev only — the "
            "keys module raises if asked to encrypt with an empty key."
        ),
    )
    agent_backend_url: str = Field(
        default="http://127.0.0.1:9080",
        description="Base URL of the developer's agent backend to proxy "
        "(env PLATFORM_AGENT_BACKEND_URL).",
    )
    host: str = "127.0.0.1"
    port: int = 9000
    log_level: str = "info"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
