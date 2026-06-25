"""HexKit contract wrapper for the ITSM change-request agent.

Resolves the OpenAI key, picks the plain or HexGate-gated path, and projects each
LangChain event into a native event. The agent lives in ``itsm_agent``; ownership
keys off the caller's **name** (HexKit never forwards email — see ``itsm_db``).
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from agent_server import protocol

logger = logging.getLogger("agent_server.itsm")


class ItsmAgent:
    framework = "langchain"

    async def run(
        self, *, input: dict[str, Any], context: dict[str, Any]
    ) -> AsyncIterator[dict]:
        # ChatOpenAI (the model backend) reads OPENAI_API_KEY from the env.
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            yield protocol.error(
                "No OpenAI API key available. Set OPENAI_API_KEY in the "
                "agent-server .env (or the process environment)."
            )
            return

        # Lazy import so a missing deepagents/hexgate install doesn't break the
        # roster — only picking the ITSM agent pays the import cost.
        from . import itsm_agent

        # HexGate-gated whenever configured; plain graph otherwise.
        if os.getenv("HEXGATE_KEY"):
            # `name` / `role` ride in `context.user` (CONTRACT.md §5); fall back to
            # a static identity for standalone runs that send no user block.
            caller = protocol.caller(context)
            identity = caller.get("name") or "hexkit-demo"
            role = caller.get("role") or os.getenv("HEXGATE_ROLE", "requester")
            events = itsm_agent.stream_as(input, user_id=identity, role=role)
        else:
            events = itsm_agent.stream(input)

        try:
            async for event in events:
                native_event = itsm_agent.to_native_event(event)
                if native_event is not None:
                    yield native_event
        except Exception as exception:  # noqa: BLE001 — degrade to a visible error event
            logger.exception("itsm run failed")
            yield protocol.error(f"agent failed: {exception}")
