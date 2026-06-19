"""Per-user agent access.

A user's `agents` column is an allow-list of agent ids:

  - ``None`` / empty  → **unrestricted**: every agent in the roster (the default
    for sign-ups and any non-seeded account).
  - a non-empty list  → exactly those agents, plus any in ``COMMON_AGENT_IDS``.

`COMMON_AGENT_IDS` is the set every user can reach regardless of their list —
empty today; this is the one-line hook for a future shared agent (e.g. add
``"hr"`` here and every account gains the HR agent).

Enforced proxy-side: the roster (`GET /agents`) is filtered to the accessible
set, and the agent-scoped routes (`/ui`, `/actions`, conversation creation)
reject the rest. The agent backend never sees this — it's a HexUI concern.
"""

from __future__ import annotations

from collections.abc import Iterable

from .models.user import User

# Agents every user can reach regardless of their allow-list. Empty for now;
# add the shared HR agent id here when it lands.
COMMON_AGENT_IDS: set[str] = set()


def can_access(user: User, agent_id: str) -> bool:
    """Whether `user` may reach `agent_id`. No allow-list = unrestricted."""
    if not user.agents:
        return True
    return agent_id in set(user.agents) | COMMON_AGENT_IDS


def accessible_ids(user: User, all_ids: Iterable[str]) -> set[str]:
    """The subset of `all_ids` this user may reach."""
    if not user.agents:
        return set(all_ids)
    return (set(user.agents) | COMMON_AGENT_IDS) & set(all_ids)
