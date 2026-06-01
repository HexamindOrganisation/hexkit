"""
Shared test fixtures.

Strategy: a single in-memory SQLite database, schema built once per session
via `Base.metadata.create_all`, tables truncated between tests. SQLite via
`aiosqlite` is async-compatible with our `AsyncSession` code path, and
`sa.Uuid` maps to CHAR(32) automatically — no driver gymnastics.

The Alembic migrations stay authoritative for Postgres production; tests
bypass them on purpose so a schema change doesn't require a migration to
unblock the suite.
"""

from __future__ import annotations

import asyncio
import os
from typing import AsyncIterator

from cryptography.fernet import Fernet

# Provision the Fernet master key BEFORE platform_backend imports — its
# Settings object is lru-cached at first read, so the env var must exist
# by then. `setdefault` lets a developer override via the shell env.
os.environ.setdefault("PLATFORM_FERNET_KEY", Fernet.generate_key().decode())

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_backend import db as db_mod
from platform_backend.db import Base
from platform_backend.models import User  # noqa: F401 — registers on metadata
from platform_backend.server import create_app


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """One event loop per session so the in-memory SQLite engine survives
    across tests. (Default per-function loop would discard it.)"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _engine():
    """Build the engine + schema once per session."""
    engine = db_mod.init_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await db_mod.dispose_engine()


@pytest_asyncio.fixture(autouse=True)
async def _truncate_tables():
    """Wipe every table between tests so each one starts clean."""
    yield
    factory = db_mod.session_factory()
    async with factory() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(text(f"DELETE FROM {table.name}"))
        await session.commit()


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Direct DB access for assertions; route handlers use their own session
    via the FastAPI dep."""
    factory = db_mod.session_factory()
    async with factory() as s:
        yield s


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """ASGI client driving the real app (lifespan does NOT run here — the
    engine is already initialized by the session fixture above)."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
