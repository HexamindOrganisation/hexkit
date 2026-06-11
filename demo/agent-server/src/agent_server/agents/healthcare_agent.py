"""Healthcare clinical-assistant agent — the developer-side artifact.

Pure OpenAI Agents SDK code: the tools, the ``agent``, and how you invoke it.
Nothing here knows about HexaUI — no SSE, no event projection, no platform
contract. Vendored from ``hexgate/examples/healthcare_agent.py`` (minus the
demo ``main``); the HexaUI contract glue lives next door in ``openai_agents.py``.

Two invocation helpers put the security story side by side:

* ``run(input)``            — the plain OpenAI Agents SDK (``agents.Runner``).
* ``run_as(input, role=…)`` — the SAME agent gated by HexGate policy. The only
  differences are ``HexgateRunner`` in place of ``Runner`` and a ``User(role=…)``
  scope; the streamed events are identical, so a forwarder written for the plain
  SDK works unchanged.

Run it standalone, no HexaUI:

    python -m agent_server.agents.healthcare_agent

(needs ``OPENAI_API_KEY``, and for ``run_as`` also ``HEXGATE_KEY``, in env/.env).
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from agents import Agent, Runner, function_tool


# ── Tools — stubs, verbatim from the upstream example ────────────────────────


@function_tool
def get_patient_record(patient_id: str) -> str:
    """Return the full clinical record (demographics, problem list, meds) for patient_id."""
    return (
        f"(stub) patient {patient_id}: Jane Doe, 47F, problem list: T2DM, HTN; "
        f"active meds: metformin 1000mg BID, lisinopril 10mg QD."
    )


@function_tool
def view_lab_results(patient_id: str) -> str:
    """Return the most recent lab panel for patient_id."""
    return (
        f"(stub) patient {patient_id} labs: A1c 7.8%, eGFR 88, "
        f"LDL 132 mg/dL (drawn 2026-05-30)."
    )


@function_tool
def order_lab_test(patient_id: str, test: str) -> str:
    """Order lab `test` (e.g. 'CBC', 'CMP', 'lipid panel') for patient_id."""
    return f"(stub) ordered {test} for patient {patient_id} → LAB-7781"


@function_tool
def prescribe(patient_id: str, drug: str, dose: str) -> str:
    """Prescribe a medication for patient_id."""
    return f"(stub) prescribed {drug} {dose} for patient {patient_id} → RX-4410"


@function_tool
def share_record(patient_id: str, recipient_email: str, recipient_domain: str) -> str:
    """Share patient_id's record with an external recipient.

    Pass the recipient's email and, separately, just the domain portion
    (the part after the @) as recipient_domain. Re-derive the true domain
    from the address and refuse on any mismatch so the gated value can't be
    decoupled from where the record actually goes.
    """
    actual_domain = recipient_email.rsplit("@", 1)[-1].strip().lower()
    if "@" not in recipient_email or actual_domain != recipient_domain.strip().lower():
        return (
            f"(stub) REFUSED: recipient_domain {recipient_domain!r} does not "
            f"match the address {recipient_email!r} — PHI not shared."
        )
    return f"(stub) shared patient {patient_id} record with {recipient_email}"


@function_tool
def get_billing_summary(patient_id: str) -> str:
    """Return the billing/claims summary (charges, payer, balance) for patient_id."""
    return (
        f"(stub) patient {patient_id} billing: payer=Aetna PPO, "
        f"outstanding balance $240.00, last claim CLM-5521 (paid)."
    )


# ── The agent — one definition, identical to the upstream example ────────────

agent = Agent(
    name="healthcare_agent",
    instructions=(
        "You are a clinical assistant in a hospital EHR. Help authorized "
        "staff look up patient records, review labs, order tests, prescribe "
        "medications, and share records. When sharing a record, pass the "
        "recipient's email domain separately. You normally do not need to "
        "ask the user to confirm before invoking a tool — act directly on "
        "the details given in their message rather than echoing them back "
        "for approval. Always respond in the same language as the user's message."
    ),
    tools=[
        get_patient_record,
        view_lab_results,
        order_lab_test,
        prescribe,
        share_record,
        get_billing_summary,
    ],
    model="gpt-4o-mini",
)


# ── Invocation ───────────────────────────────────────────────────────────────


async def run(input: Any) -> AsyncIterator[Any]:
    """Stream the agent with the plain OpenAI Agents SDK runner.

    ``input`` is whatever ``Runner.run_streamed`` accepts — a prompt string or a
    transcript (list of role/content items). Yields the SDK's native
    ``stream_events()`` items.
    """
    result = Runner.run_streamed(agent, input)
    async for event in result.stream_events():
        yield event


async def run_as(input: Any, *, role: str) -> AsyncIterator[Any]:
    """Stream the agent through HexGate as ``role`` — the same call as :func:`run`.

    The only differences from the plain SDK path: ``HexgateRunner`` (which gates
    every tool call against the policy the platform resolves for the agent's
    name) instead of ``Runner``, and a ``User(role=…)`` scope. The yielded events
    are identical, so the forwarder/translator is none the wiser.

    ``HexgateRunner()`` reads ``HEXGATE_KEY`` from the environment (loaded from
    the agent-server's ``.env`` at startup).
    """
    from hexgate.adapters.openai import HexgateRunner
    from hexgate.runtime import User

    user = User(user_id="hexaui-demo", session_id="hexaui-demo", role=role)
    result = HexgateRunner().run_streamed(agent, input, user=user)
    async for event in result.stream_events():
        yield event


if __name__ == "__main__":
    # Standalone demo — plain OpenAI Agents SDK wrapped by HexGate, no HexaUI.
    import asyncio

    try:
        from dotenv import load_dotenv

        load_dotenv()  # best-effort: pick up OPENAI_API_KEY / HEXGATE_KEY
    except ImportError:
        pass

    async def _demo() -> None:
        prompt = "Show the full record for patient 88."
        async for event in run_as(prompt, role="nurse"):
            print(event)

    asyncio.run(_demo())
