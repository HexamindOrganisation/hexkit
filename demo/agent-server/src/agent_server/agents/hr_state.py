"""Minimal in-memory store for the HR self-service time-off tools.

Process-global, single-process — fine for the demo (like ``devops_state`` /
``itsm_db``). Keyed by the caller's name so each employee only ever sees their
own balance and requests. Pending requests don't deduct the balance (there's no
approval step in this cut).
"""

from __future__ import annotations

from typing import Any

# Default annual allowance every employee starts with, in days.
_DEFAULT_BALANCE = {"conges_payes": 25.0, "rtt": 12.0, "sick": 5.0}

# name -> list of their time-off requests
_REQUESTS: dict[str, list[dict[str, Any]]] = {}
_counter = 0


def leave_balance(name: str) -> dict[str, float]:
    """Remaining leave (days) per type for `name`."""
    return dict(_DEFAULT_BALANCE)


def add_request(
    name: str, *, start_date: str, end_date: str, leave_type: str
) -> dict[str, Any]:
    """Record a new pending time-off request for `name`."""
    global _counter
    _counter += 1
    request = {
        "id": f"LEAVE-{_counter:04d}",
        "employee": name,
        "type": leave_type,
        "start": start_date,
        "end": end_date,
        "status": "pending",
    }
    _REQUESTS.setdefault(name, []).append(request)
    return request


def list_requests(name: str) -> list[dict[str, Any]]:
    """Every time-off request `name` has submitted."""
    return _REQUESTS.get(name, [])
