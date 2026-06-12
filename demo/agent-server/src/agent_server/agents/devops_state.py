"""Shared, in-memory service state for the DevOps demo.

The single source of truth behind the DevOps UI panel: a per-environment map of
services (status, replicas, version, uptime). The agent's tools mutate it
(restart/scale/delete) and the widget actions read it (select_env + summary +
table), so the panel reflects what the model just did. Process-global, single
user — fine for the demo, like ``actions.py``.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Any

ENVS = ["dev", "staging", "prod"]
SERVICES = ["web", "checkout", "payments", "search", "auth"]

# Per service: replicas (dev, staging, prod) and the running version (same across
# stages). Hot-path services run more replicas in prod.
_SPEC: dict[str, dict[str, Any]] = {
    "web": {"replicas": (1, 2, 6), "version": "v2.4.0"},
    "checkout": {"replicas": (1, 2, 5), "version": "v2.4.0"},
    "payments": {"replicas": (1, 2, 4), "version": "v2.3.7"},
    "search": {"replicas": (1, 1, 3), "version": "v1.9.2"},
    "auth": {"replicas": (1, 2, 4), "version": "v3.1.0"},
}

# Seed uptime per env, per service. dev redeploys often (minutes/hours); prod is
# stable (days/weeks); payments@prod has only been up ~20m — it's flapping (and
# is seeded degraded), so "restart payments in prod" is a tidy demo.
_SEED_AGE = {
    "dev": {"web": timedelta(hours=2), "checkout": timedelta(minutes=35), "payments": timedelta(hours=1), "search": timedelta(minutes=12), "auth": timedelta(hours=3)},
    "staging": {"web": timedelta(days=1, hours=4), "checkout": timedelta(hours=20), "payments": timedelta(hours=6), "search": timedelta(days=2), "auth": timedelta(hours=9)},
    "prod": {"web": timedelta(days=18), "checkout": timedelta(days=9), "payments": timedelta(minutes=20), "search": timedelta(days=31), "auth": timedelta(days=12)},
}

_ENV_INDEX = {"dev": 0, "staging": 1, "prod": 2}


def _seed() -> dict[str, dict[str, dict[str, Any]]]:
    now = datetime.now()
    state: dict[str, dict[str, dict[str, Any]]] = {}
    for env in ENVS:
        index = _ENV_INDEX[env]
        state[env] = {}
        for name in SERVICES:
            degraded = env == "prod" and name == "payments"
            state[env][name] = {
                "status": "degraded" if degraded else "healthy",
                "replicas": _SPEC[name]["replicas"][index],
                "version": _SPEC[name]["version"],
                "started_at": now - _SEED_AGE[env][name],
            }
    return state


_STATE = _seed()
_selected_env = "dev"


# ── Selection (driven by the env buttons) ─────────────────────────────────────


def select_env(env: str) -> None:
    global _selected_env
    if env in ENVS:
        _selected_env = env


def selected_env() -> str:
    return _selected_env


# ── Mutations (called by the agent's tools) ───────────────────────────────────


def restart(service: str, env: str) -> None:
    svc = _STATE.get(env, {}).get(service)
    if svc is not None:
        svc["status"] = "healthy"
        svc["started_at"] = datetime.now()  # uptime resets → "just now"
        if svc["replicas"] == 0:  # recovering a down service → bring its pods back
            svc["replicas"] = _SPEC[service]["replicas"][_ENV_INDEX[env]]


def scale(service: str, replicas: int, env: str) -> None:
    svc = _STATE.get(env, {}).get(service)
    if svc is not None:
        svc["replicas"] = max(0, int(replicas))


def delete(name: str, env: str) -> None:
    # Mark the service down (kept visible in the table) rather than dropping the
    # row — the impact reads better. A later restart brings it back healthy.
    svc = _STATE.get(env, {}).get(name)
    if svc is not None:
        svc["status"] = "down"
        svc["replicas"] = 0


# ── Reads (the widget data sources) ───────────────────────────────────────────


def summary(env: str) -> dict[str, int]:
    services = _STATE.get(env, {}).values()
    return {
        "healthy": sum(1 for s in services if s["status"] == "healthy"),
        "degraded": sum(1 for s in services if s["status"] != "healthy"),
        "replicas": sum(s["replicas"] for s in services),
    }


def table_csv(env: str) -> str:
    now = datetime.now()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Service", "Status", "Replicas", "Version", "Uptime"])
    services = _STATE.get(env, {})
    for name in SERVICES:  # stable order
        svc = services.get(name)
        if svc is None:
            continue
        uptime = "—" if svc["status"] == "down" else _format_age(now - svc["started_at"])
        writer.writerow([name, svc["status"], svc["replicas"], svc["version"], uptime])
    return buf.getvalue()


def _format_age(delta: timedelta) -> str:
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    if days < 14:
        return f"{days}d"
    return f"{days // 7}w"
