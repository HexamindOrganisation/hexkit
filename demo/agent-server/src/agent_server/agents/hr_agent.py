"""HR (RH) assistant agent — RBAC with field-level scoping (LangChain).

Vendored from ``hexgate/examples/hr_agent.py``; the HexaUI wrapper is ``hr.py``.
One agent definition — the caller's ROLE flips every decision via the platform
policy (resolved by agent name ``hr_agent``; source in
``hexgate/examples/hr_policy.yaml``). The escalation ladder, least → most
privileged: ``default < manager < gestionnaire_rh``.

The policy does the gating on each tool call:

  - field-level scoping on one read tool — ``get_employee_data`` takes a ``field``
    arg, and each role widens the allowed ``args.field`` allowlist;
  - the ultra-sensitive medical read is its own tool (``get_medical_leave``) so it
    gates separately; salary writes, the aggregated payroll view, and offboarding
    are gestionnaire_rh-only; ``export_payroll`` declares a payslip ``count`` the
    policy caps per role, so an over-limit export is denied at the gate. The cap
    bounds the volume the agent *declares* — not a model that under-reports it; a
    real export would derive ``count`` server-side from the actual selection
    rather than trust the model's estimate.

The tools are stubs (no datastore) — the demo is about the policy, not the data.
``stream`` / ``stream_as`` yield LangChain ``astream_events`` items the proxy's
LangChain translator normalizes (projection shared via ``langchain_events``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from . import hr_state
from .langchain_events import messages_input, to_native_event  # noqa: F401

# Load .env at import — the eager `agent` below (which `hexgate register`
# resolves) needs OPENAI_API_KEY at ChatOpenAI construction time.
load_dotenv()


def _actor() -> str:
    """The calling employee's NAME from the active User scope (the self-service
    tools act on this, never a model-supplied id). Falls back to a demo identity
    on the ungated path, where no User scope is set."""
    from hexgate.runtime import get_current_user

    user = get_current_user()
    return user.user_id if user is not None else "hexui-demo"


# ---------------------------------------------------------------------------
# Tools — stubs (no datastore), so the only gating they demonstrate is the
# policy's arg-level check on each call's `args` (e.g. `args.field`, `args.count`).
# Checks the constraint engine can't express — row-level "son équipe" scope,
# name → id resolution — would live in the tool body keyed off the trusted User
# identity (as the ITSM agent does via `_actor`); these stubs deliberately don't
# implement them, so a caller is bounded by field-by-role gating only, NOT by
# which employees are theirs to see.
# ---------------------------------------------------------------------------


@tool
def search_directory(name: str) -> str:
    """Look up an employee in the internal directory by name.

    Returns non-sensitive annuaire fields only (title, department, manager,
    work email). Never returns salary, bank, or medical data.
    """
    return (
        f"(stub) annuaire — {name}: id=E1042, Responsable Marketing, "
        f"service Marketing, manager=Paul Durand, "
        f"work_email={name.split()[0].lower()}@acme.example"
    )


@tool
def get_employee_data(employee_id: str, field: str) -> str:
    """Return a single FIELD of an employee record.

    `field` is one of: title, department, manager, work_email, leave_balance,
    performance_rating, salary, contract, bank_account. Which fields a caller
    may read is decided by the policy from their role — pass the field the
    user asked for and let the policy gate it. Health data is NOT available
    here; use get_medical_leave for that.
    """
    sample = {
        "title": "Responsable Marketing",
        "department": "Marketing",
        "manager": "Paul Durand",
        "work_email": "sophie.martin@acme.example",
        "leave_balance": "18.5 jours",
        "performance_rating": "3,8 / 5 (cycle 2025)",
        "salary": "54 000 € brut/an",
        "contract": "CDI, temps plein, depuis 2021-03-01",
        "bank_account": "FR76 3000 4000 0512 3456 7890 143",
    }
    value = sample.get(field, f"<champ inconnu: {field}>")
    return f"(stub) employee {employee_id} — {field}: {value}"


@tool
def get_medical_leave(employee_id: str) -> str:
    """Return current medical / sick-leave information for an employee.

    Health data is the most sensitive category (RGPD). It lives in its own
    tool on purpose so it can be gated separately from the rest of the
    employee record.
    """
    return (
        f"(stub) employee {employee_id}: arrêt maladie en cours du "
        f"2026-06-02 au 2026-06-27 (motif non communiqué)."
    )


@tool
def update_salary(employee_id: str, new_amount: float) -> str:
    """Set an employee's gross annual salary to `new_amount` (in euros)."""
    return (
        f"(stub) salaire de l'employé {employee_id} mis à jour → "
        f"{new_amount:,.0f} € brut/an"
    )


@tool
def view_compensation(team: str) -> str:
    """Return the aggregated compensation grid / payroll mass for a team."""
    return (
        f"(stub) équipe {team}: masse salariale 1 245 000 €/an, "
        f"effectif 17, salaire médian 58 000 €, P90 92 000 €."
    )


@tool
def export_payroll(period: str, count: int) -> str:
    """Export `count` payslips for the given `period` (e.g. '2026-01').

    Pass `count` = the number of payslips the export would produce. The policy
    enforces a per-role ceiling on `count`, so an export whose declared volume
    exceeds the caller's limit is denied at the gate. This bounds the volume the
    agent *declares*, not a model that under-reports `count` — a real export
    would derive `count` server-side from the actual selection rather than trust
    the model's estimate.
    """
    if count <= 0:
        return "(stub) export refusé — `count` doit être un entier positif."
    return f"(stub) export de {count} bulletins de paie pour {period} → PAY-EXP-3391"


@tool
def offboard_employee(employee_id: str) -> str:
    """Trigger the offboarding (departure) procedure for an employee."""
    return (
        f"(stub) procédure de départ déclenchée pour l'employé "
        f"{employee_id} → OFFB-2207"
    )


# ── Self-service (the calling employee acts on their OWN record) ─────────────
# These take no employee_id — they operate on the trusted caller identity
# (`_actor`), so an employee can only ever see/request against themselves.


@tool
def get_my_leave_balance() -> str:
    """Return the calling employee's own remaining leave balance, in days."""
    name = _actor()
    balance = hr_state.leave_balance(name)
    days = ", ".join(f"{kind}: {amount} j" for kind, amount in balance.items())
    return f"(stub) {name} — solde de congés → {days}"


@tool
def request_time_off(start_date: str, end_date: str, leave_type: str = "conges_payes") -> str:
    """Submit a time-off request for the calling employee.

    `start_date` / `end_date` are ISO dates (YYYY-MM-DD); `leave_type` is one of
    conges_payes, rtt, sick, unpaid. The request is recorded as 'pending'.
    """
    name = _actor()
    request = hr_state.add_request(
        name, start_date=start_date, end_date=end_date, leave_type=leave_type
    )
    return (
        f"(stub) demande {request['id']} créée pour {name} — {leave_type} "
        f"du {start_date} au {end_date} (statut: {request['status']})."
    )


@tool
def list_my_time_off() -> str:
    """List the calling employee's own time-off requests and their status."""
    name = _actor()
    requests = hr_state.list_requests(name)
    if not requests:
        return f"(stub) aucune demande de congés pour {name}."
    lines = [
        f"{r['id']} [{r['status']}] {r['type']} {r['start']} → {r['end']}"
        for r in requests
    ]
    return f"(stub) demandes de {name}:\n" + "\n".join(lines)


TOOLS = [
    search_directory,
    get_employee_data,
    get_medical_leave,
    update_salary,
    view_compensation,
    export_payroll,
    offboard_employee,
    # self-service
    get_my_leave_balance,
    request_time_off,
    list_my_time_off,
]

INSTRUCTIONS = (
    "Tu es un assistant RH. Tu aides le personnel autorisé à consulter "
    "l'annuaire, lire les champs d'un dossier salarié, modifier une "
    "rémunération, exporter des bulletins de paie, consulter la compensation "
    "agrégée et déclencher un offboarding. Quand l'utilisateur demande un "
    "champ précis d'un dossier, appelle get_employee_data avec ce champ exact "
    "(title, department, manager, work_email, leave_balance, "
    "performance_rating, salary, contract, bank_account) ; pour les arrêts "
    "maladie, utilise get_medical_leave. Si l'utilisateur désigne un salarié "
    "par son nom, passe ce nom directement comme employee_id. Pour un export, "
    "estime le nombre de bulletins (count) à partir de la demande. Pour les "
    "demandes en libre-service de l'utilisateur sur SON propre dossier — solde "
    "de congés, poser des congés, suivre ses demandes — utilise "
    "get_my_leave_balance, request_time_off et list_my_time_off (ces outils "
    "agissent sur l'appelant, ne demande pas d'identifiant). Tu n'as pas "
    "besoin de demander confirmation avant d'appeler un outil — agis "
    "directement sur les détails fournis. Utilise toujours un outil pour toute "
    "consultation ou action RH, et fonde-toi uniquement sur le résultat des "
    "outils comme source de vérité, jamais sur l'historique de la conversation. "
    "La couche de politique gate les actions sensibles, fais-lui confiance pour "
    "bloquer ce qui n'est pas autorisé. Réponds toujours dans la langue du "
    "message de l'utilisateur."
)


# Built at import so `hexgate register` can resolve `…hr_agent:agent`;
# `stream_as` wraps it with HexGate policy enforcement at call time.
def _build_agent() -> Any:
    from langgraph.prebuilt import create_react_agent

    built = create_react_agent(
        model=ChatOpenAI(model="gpt-4o-mini", temperature=0),
        tools=TOOLS,
        prompt=INSTRUCTIONS,
    )
    built.name = "hr_agent"  # policy + manifest resolve by this name on the platform
    return built


agent = _build_agent()

# Enforced wrapper, built once on first gated use — `wrap_langchain_agent`
# mutates TOOLS in place, so re-running it per request would re-wrap them.
# One wrapper serves all users; `user` is passed per call.
_enforced: Any | None = None


def _enforced_agent() -> Any:
    global _enforced
    if _enforced is None:
        from hexgate.adapters.langchain import wrap_langchain_agent

        _enforced = wrap_langchain_agent(agent=agent, tools=TOOLS)
    return _enforced


# Invocation — yield LangChain astream_events items for the proxy (event
# projection + input coercion shared with the ITSM agent in `langchain_events`).


async def stream(input: Any) -> AsyncIterator[Any]:
    """Stream the plain (ungated) graph, yielding astream_events items."""
    async for event in agent.astream_events(messages_input(input), version="v2"):
        yield event


async def stream_as(input: Any, *, user_id: str, role: str) -> AsyncIterator[Any]:
    """Same as :func:`stream`, but policy-gated against the caller — ``role``
    (default < manager < gestionnaire_rh) flips each decision."""
    from hexgate.runtime import User

    user = User(user_id=user_id, role=role, session_id="hexui-demo-hr")
    async for event in _enforced_agent().astream_events(
        messages_input(input), user=user
    ):
        yield event
