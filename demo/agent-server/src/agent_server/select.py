"""Pick the agent implementation for a request.

One entry per org agent. Each wrapper picks its own plain-vs-HexGate path
internally, and is imported lazily so a missing framework/hexgate install only
affects the agent that needs it — not the whole roster.
"""

from __future__ import annotations

from typing import Any

from .base import Agent


def select_agent(agent_id: str, context: dict[str, Any]) -> Agent:
    if agent_id == "healthcare":
        from .agents.clinic_org.healthcare.healthcare import HealthcareAgent

        return HealthcareAgent()

    if agent_id == "devops":
        from .agents.tech_org.devops.devops import DevopsAgent

        return DevopsAgent()

    if agent_id == "itsm":
        from .agents.tech_org.itsm.itsm import ItsmAgent

        return ItsmAgent()

    if agent_id == "hr":
        from .agents.shared.hr.hr import HrAgent

        return HrAgent()

    # The route validates agent_id against the roster before calling this, so an
    # unmapped id here means the roster and this dispatch are out of sync.
    raise ValueError(f"No agent implementation for '{agent_id}'")
