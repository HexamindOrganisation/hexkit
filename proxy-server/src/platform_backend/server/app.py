"""FastAPI app factory + lifespan.

Mirrors `platform_runtime.server.app.create_app`: a single factory that wires
routers + lifespan. The lifespan owns the engine — created on startup,
disposed on shutdown.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .. import runtime_client
from ..auth.demo_users import DemoUsersError, load_demo_users
from ..config import get_settings
from ..db import dispose_engine, init_engine
from ..routes import auth as auth_routes
from ..routes import chat as chat_routes
from ..routes import conversations as conversations_routes
from ..routes import files as files_routes
from ..routes import folders as folders_routes
from ..routes import me as me_routes
from ..routes import proxy as proxy_routes

logger = logging.getLogger("platform_backend.server")


def _alembic_upgrade_head(database_url: str) -> None:
    """Bring `database_url` to the latest revision using the project's Alembic
    migrations. Runs synchronously (Alembic spins its own loop), so call it via
    `asyncio.to_thread` from the async lifespan. Paths are resolved absolutely
    so it works regardless of the process's working directory.
    """
    from alembic import command
    from alembic.config import Config

    proxy_root = Path(__file__).resolve().parents[3]  # …/proxy-server
    cfg = Config(str(proxy_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(proxy_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        engine = init_engine()
        # SQLite (zero-infra dev path) migrates to head on startup so a pull
        # with new migrations is picked up on restart; Postgres is migrated
        # out-of-band by design.
        if engine.url.get_backend_name() == "sqlite":
            await asyncio.to_thread(
                _alembic_upgrade_head,
                engine.url.render_as_string(hide_password=False),
            )
        # Optional: upsert pre-defined demo accounts from a YAML file so a
        # fresh DB ships with a handful of users ready to log in (Alice the
        # billing-role, Bob the support-role, etc.). Opt-in via
        # PLATFORM_DEMO_USERS_FILE; missing file or env unset = no seeding.
        demo_path = get_settings().demo_users_file
        if demo_path:
            try:
                await load_demo_users(Path(demo_path))
            except DemoUsersError as e:
                logger.error("demo users file rejected: %s", e)
                raise
        runtime_client.init_client()
        logger.info("platform_backend ready")
        try:
            yield
        finally:
            await runtime_client.dispose_client()
            await dispose_engine()

    app = FastAPI(title="platform-backend", version="0.1.0", lifespan=lifespan)
    app.include_router(auth_routes.router)
    app.include_router(me_routes.router)
    app.include_router(files_routes.router)
    app.include_router(folders_routes.router)
    app.include_router(conversations_routes.router)
    app.include_router(chat_routes.router)
    app.include_router(proxy_routes.router)
    return app
