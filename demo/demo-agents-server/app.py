import asyncio
from fastapi import FastAPI

from .server.agent_routes import router as agents_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="HexaUI demo Agent Server",
        description="A demo server for showcasing Hexgate and UI integration, not a full reference implementation",
        version="0.1.0",
    )
    # In-memory run registry: run_id -> cancel Event, populated by the stream
    # route and consulted by the cancel route. Process-local — a multi-worker
    # deployment would need a shared store. Initialized at app-creation time so
    # it exists even when the lifespan hasn't run (e.g. unit tests).
    app.state.runs: dict[str, asyncio.Event] = {}
    app.include_router(agents_router)

    @app.get("/")
    async def root() -> dict:
        return {"service": "agent-server", "agents": "/agents"}

    return app
