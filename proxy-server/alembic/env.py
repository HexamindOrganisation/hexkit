"""
Alembic environment.

The database URL is read from `PLATFORM_DATABASE_URL` rather than
`alembic.ini` so the same migration command works in dev, tests, and
production without editing files. `prepend_sys_path = src` in alembic.ini
puts the `platform_backend` package on the path so we can import its
metadata for autogenerate.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context

# Import the package so all model modules register their tables on Base.metadata.
from platform_backend import models  # noqa: F401 — side-effect import
from platform_backend.db import Base
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the URL from env at runtime. asyncpg can't run inside Alembic's sync
# offline mode, so for `--sql` we substitute a sync driver.
_url = os.environ.get("PLATFORM_DATABASE_URL")
if _url:
    config.set_main_option("sqlalchemy.url", _url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url") or ""
    # `--sql` mode emits SQL without connecting; swap the async driver for a
    # sync one purely for offline rendering. Online migrations still use asyncpg.
    sync_url = url.replace("+asyncpg", "")
    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # SQLite can't ALTER/DROP columns in place; batch mode rewrites the table so
    # the same migrations run on both SQLite (dev) and Postgres.
    render_as_batch = connection.dialect.name == "sqlite"
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=render_as_batch,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
