"""HexKit contract wrapper for the healthcare agent.

Resolves the OpenAI key, picks the plain or HexGate-gated path, and forwards each
SDK event as a native event. The agent itself lives in ``healthcare_agent``;
event projection in ``openai_agents``.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from agents import set_default_openai_key

from agent_server import protocol
from agent_server.frameworks.openai_agents import agent_input, to_native_event

from . import healthcare_agent

logger = logging.getLogger("agent_server.healthcare")


class HealthcareAgent:
    framework = "openai-agents"

    async def run(
        self, *, input: dict[str, Any], context: dict[str, Any]
    ) -> AsyncIterator[dict]:
        # Provider key comes from the backend's own environment.
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            yield protocol.error(
                "No OpenAI API key available. Set OPENAI_API_KEY in the "
                "agent-server .env (or the process environment)."
            )
            return
        set_default_openai_key(api_key)

        # HexGate-gated path whenever HexGate is configured; plain SDK otherwise.
        # `banned_error` is the ban exception type, resolved only on the gated
        # path so the plain path never imports the optional hexgate dependency.
        banned_error: type[Exception] | None = None
        if os.getenv("HEXGATE_API_KEY"):
            from hexgate.security import AgentBannedError as banned_error

            # Scope policy decisions to the signed-in HexKit user. `id` / `role`
            # ride in `context.user` (CONTRACT.md §5); fall back to the static
            # demo identity and HEXGATE_ROLE for standalone runs that send no
            # user block.
            caller = protocol.caller(context)
            user_id = caller.get("id") or "hexkit-demo"
            role = caller.get("role") or os.getenv("HEXGATE_ROLE", "nurse")
            events = healthcare_agent.stream_as(
                agent_input(input), user_id=user_id, role=role
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
            # A kill-switch ban refuses the run before the LLM. Surface it as a
            # structured error the frontend can recognize (and localize) rather
            # than a generic failure.
            if banned_error is not None and isinstance(exception, banned_error):
                yield protocol.error(
                    exception.user_message,
                    details={
                        "code": exception.code,
                        "ban_type": exception.ban_type,
                        "target": exception.target,
                        "reason": exception.reason,
                    },
                )
                return
            logger.exception("healthcare run failed")
            yield protocol.error(f"agent failed: {exception}")
