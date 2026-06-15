"""HexaUI contract wrapper for the healthcare agent.

Resolves the OpenAI key, picks the plain or HexGate-gated path, and forwards each
SDK event as a native event. The agent itself lives in ``healthcare_agent``;
event projection in ``openai_agents``.
"""

from __future__ import annotations

import logging
import os
from typing import Any, AsyncIterator

from agents import set_default_openai_key

from .. import protocol
from . import healthcare_agent
from .openai_agents import agent_input, to_native_event

logger = logging.getLogger("agent_server.healthcare")


class HealthcareAgent:
    framework = "openai-agents"

    async def run(
        self, *, input: dict[str, Any], context: dict[str, Any]
    ) -> AsyncIterator[dict]:
        # .env key wins; fall back to the per-run key from the Settings UI.
        api_key = os.getenv("OPENAI_API_KEY") or (
            (context or {}).get("credentials") or {}
        ).get("openai_api_key")
        if not api_key:
            yield protocol.error(
                "No OpenAI API key available. Set OPENAI_API_KEY in the "
                "agent-server .env, or add one in the HexaUI Settings UI."
            )
            return
        set_default_openai_key(api_key)

        # HexGate-gated path whenever HexGate is configured; plain SDK otherwise.
        if os.getenv("HEXGATE_KEY"):
            events = healthcare_agent.stream_as(
                agent_input(input), role=os.getenv("HEXGATE_ROLE", "nurse")
            )
        else:
            events = healthcare_agent.stream(agent_input(input))

        tool_names_by_id: dict[str, str] = {}
        try:
            async for sdk_event in events:
                native_event = to_native_event(sdk_event, tool_names_by_id)
                if native_event is not None:
                    yield native_event
        except Exception as exception:  # noqa: BLE001 — degrade to a visible error event
            logger.exception("healthcare run failed")
            yield protocol.error(f"agent failed: {exception}")
