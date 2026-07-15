"""HexKit contract wrapper for the HR (RH) agent.

Resolves the OpenAI key, picks the plain or HexGate-gated path, and projects each
LangChain event into a native event. The agent lives in ``hr_agent``; the caller's
``role`` (default < manager < gestionnaire_rh) flips each policy decision.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from agent_server import protocol

logger = logging.getLogger("agent_server.hr")

# The elevated HR roles (hr_policy.yaml). Anything else — no role, or a role from
# another agent (nurse, viewer, requester…) — normalizes to the `default`
# baseline rather than passing an unrecognized string to the policy.
_HR_ROLES = {"manager", "gestionnaire_rh"}


class HrAgent:
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

        # Lazy import so a missing langchain/hexgate install doesn't break the
        # roster — only picking the HR agent pays the import cost.
        from . import hr_agent

        # HexGate-gated whenever configured; plain graph otherwise.
        if os.getenv("HEXGATE_API_KEY"):
            # `name` / `role` ride in `context.user` (CONTRACT.md §5); fall back to
            # a static identity for standalone runs that send no user block.
            caller = protocol.caller(context)
            identity = caller.get("name") or "hexkit-demo"
            role = caller.get("role") or os.getenv("HEXGATE_ROLE", "default")
            if role not in _HR_ROLES:
                role = "default"
            events = hr_agent.stream_as(input, user_id=identity, role=role)
        else:
            events = hr_agent.stream(input)

        try:
            async for event in events:
                native_event = hr_agent.to_native_event(event)
                if native_event is not None:
                    yield native_event
        except Exception as exception:  # noqa: BLE001 — degrade to a visible error event
            logger.exception("hr run failed")
            yield protocol.error(f"agent failed: {exception}")
