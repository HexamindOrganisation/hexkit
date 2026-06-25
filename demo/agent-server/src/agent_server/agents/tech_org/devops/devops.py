"""HexKit contract wrapper for the devops agent.

The agent runs on Google ADK, but its model is OpenAI via LiteLLM — which reads
``OPENAI_API_KEY`` from the environment. This resolves that key, picks the plain
or HexGate-gated path, and forwards each ADK event as a native event. The agent
itself (and the ADK ``Event`` → native projection) lives in ``devops_agent``.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from agent_server import protocol
from agent_server.frameworks.google_adk import to_native_event

from . import devops_agent

logger = logging.getLogger("agent_server.devops")

# The elevated DevOps roles (devops_policy.yaml). Anything else — no role, or a
# role from another agent (nurse, requester…) — normalizes to the `default`
# baseline (read logs) rather than passing an unrecognized string to the policy.
_DEVOPS_ROLES = {"operator", "admin"}


class DevopsAgent:
    framework = "google-adk"

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
        # LiteLLM (the ADK model backend) reads the key from the environment.
        os.environ["OPENAI_API_KEY"] = api_key

        text = protocol.last_user_text(input)
        # HexGate-gated path whenever HexGate is configured; plain ADK otherwise.
        if os.getenv("HEXGATE_KEY"):
            # Scope policy decisions to the signed-in HexKit user. `id` / `role`
            # ride in `context.user` (CONTRACT.md §5); fall back to the static
            # demo identity and HEXGATE_ROLE for standalone runs that send no
            # user block.
            caller = protocol.caller(context)
            user_id = caller.get("id") or "hexkit-demo"
            role = caller.get("role") or os.getenv("HEXGATE_ROLE", "default")
            if role not in _DEVOPS_ROLES:
                role = "default"
            events = devops_agent.stream_as(text, user_id=user_id, role=role)
        else:
            events = devops_agent.stream(text)

        try:
            async for adk_event in events:
                native_event = to_native_event(adk_event)
                if native_event is not None:
                    yield native_event
        except Exception as exception:  # noqa: BLE001 — degrade to a visible error event
            logger.exception("devops run failed")
            yield protocol.error(f"agent failed: {exception}")
