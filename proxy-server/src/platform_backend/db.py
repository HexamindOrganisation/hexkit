"""
Async SQLAlchemy engine + session factory + FastAPI dependency.

One engine per process (FastAPI lifespan owns it). Sessions are short-lived:
one per request, yielded by `get_session`, committed by the route handler,
rolled back by the dep wrapper on exception.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


def _attach_sqlite_fk_pragma(engine: AsyncEngine) -> None:
    """SQLite ignores FK constraints unless told otherwise — Postgres
    enforces them always, so flipping this for SQLite makes the two
    dialects behave the same in tests. No-op for non-sqlite engines.
    """
    if engine.url.get_backend_name() != "sqlite":
        return

    @event.listens_for(engine.sync_engine, "connect")
    def _pragma_on_connect(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class Base(DeclarativeBase):
    """Single declarative base for every model in the package."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str | None = None) -> AsyncEngine:
    """Create the global engine. Called by the FastAPI lifespan and by tests
    (which may pass a per-test database URL)."""
    global _engine, _session_factory
    url = database_url or get_settings().database_url
    _engine = create_async_engine(url, future=True, pool_pre_ping=True)
    _attach_sqlite_fk_pragma(_engine)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        # Lazy init lets tests that import models without booting the app work.
        init_engine()
    assert _session_factory is not None
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding one session per request.

    Rolls back on exception so route handlers don't have to bracket their
    own try/except. Commits are explicit (in the route handler).
    """
    factory = session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
