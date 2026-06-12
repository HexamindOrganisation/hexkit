"""DevOps / infra assistant agent — Google ADK (LiteLLM over an OpenAI model).

The tools + ``agent``, and how to invoke it: ``stream`` (plain ADK runner) and
``stream_as`` (the same agent gated by HexGate policy). Vendored from
``hexgate/examples/devops_agent.py``. The HexaUI contract wrapper that the
server runs lives in ``devops.py``; ADK ``Event`` → native projection is
``to_native_event`` below.

One agent definition; the caller's ``role`` (viewer < operator < admin) is what
flips the decision — the policy gates ``scale_deployment`` on the replica count
AND the env, and reserves ``delete_resource`` for admin.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from . import devops_state


# ── Tools — stubs from the upstream example; the write tools also update the
#    shared service state so the UI panel reflects what the model just did. ────


def read_logs(service: str, env: str) -> str:
    """Return the most recent log lines for `service` in environment `env`.

    `env` is one of "dev", "staging", "prod".
    """
    return (
        f"(stub) {service}@{env} last 3 lines:\n"
        f"  12:01:04 INFO  request id=ab12 status=200 latency=42ms\n"
        f"  12:01:05 WARN  upstream payments slow (peer=2)\n"
        f"  12:01:06 INFO  request id=ab13 status=200 latency=51ms"
    )


def restart_service(service: str, env: str) -> str:
    """Restart `service` in environment `env` (one of dev/staging/prod)."""
    devops_state.restart(service, env)
    return f"(stub) restarted {service}@{env} → rollout OPS-2210 complete"


def scale_deployment(service: str, replicas: int, env: str) -> str:
    """Scale `service` to `replicas` pods in environment `env`.

    `replicas` is an integer; `env` is one of dev/staging/prod. The policy
    gates this on BOTH the replica count (a per-role cap) and the env, so
    the same call can pass for one role and fail for another.
    """
    devops_state.scale(service, replicas, env)
    return f"(stub) scaled {service}@{env} to {replicas} replicas → OPS-2211"


def delete_resource(name: str, env: str) -> str:
    """Permanently delete resource `name` in environment `env`.

    Destructive and irreversible — the policy allows it only for the
    highest-privilege role and denies it outright for everyone else.
    """
    devops_state.delete(name, env)
    return f"(stub) deleted {name}@{env} → OPS-2212"


# ── The agent — one definition, identical to the upstream example ────────────

agent = Agent(
    name="devops_agent",
    model=LiteLlm(model="openai/gpt-4o-mini"),
    instruction=(
        "You are a DevOps assistant operating a Kubernetes platform. Help "
        "authorized engineers read service logs, restart services, scale "
        "deployments, and delete resources. Map the user's request to the "
        "right tool, pulling the service/resource name, the replica count, "
        "and the environment (one of dev/staging/prod) straight from their "
        "message. You normally do not need to ask the user to confirm "
        "before invoking a tool — act directly on the details given rather "
        "than echoing them back for approval. The policy layer is what "
        "gates sensitive actions, so trust it to stop anything you're not "
        "allowed to do. Always respond in the same language as the user's message."
    ),
    tools=[
        read_logs,
        restart_service,
        scale_deployment,
        delete_resource,
    ],
)


# ── Invocation ───────────────────────────────────────────────────────────────

_APP_NAME = "devops_agent"
_USER_ID = "hexui-demo"
_SESSION_ID = "hexui-demo-devops"


def _message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


async def stream(text: str) -> AsyncIterator[Any]:
    """Run the agent with the plain ADK runner, yielding ADK ``Event`` objects."""
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=_APP_NAME, user_id=_USER_ID, session_id=_SESSION_ID
    )
    runner = Runner(agent=agent, app_name=_APP_NAME, session_service=session_service)
    async for event in runner.run_async(
        user_id=_USER_ID, session_id=_SESSION_ID, new_message=_message(text)
    ):
        yield event


async def stream_as(text: str, *, role: str) -> AsyncIterator[Any]:
    """Same as :func:`stream`, but through HexGate as ``role`` — every tool call is
    policy-gated. ``HexgateRunner`` reads ``HEXGATE_KEY`` from the environment.
    """
    from hexgate.adapters.google import HexgateRunner
    from hexgate.runtime import User

    user = User(user_id=_USER_ID, session_id=_SESSION_ID, role=role)
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=_APP_NAME, user_id=user.user_id, session_id=user.session_id
    )
    runner = HexgateRunner(agent=agent, app_name=_APP_NAME, session_service=session_service)
    async for event in runner.run_async(new_message=_message(text), user=user):
        yield event


# ── ADK Event → HexaUI native event ──────────────────────────────────────────


def to_native_event(event: Any) -> dict | None:
    """Project one ADK ``Event`` into the native JSON the proxy's
    ``GoogleADKTranslator`` reads (``None`` to drop it).

    Mirrors the wire shape the translator expects: ``author`` + ``content.parts``
    of ``text`` / ``function_call`` / ``function_response``, with ``partial`` and
    ``turn_complete`` carried through so block framing stays correct.
    """
    content = getattr(event, "content", None)
    raw_parts = getattr(content, "parts", None) or []

    parts: list[dict] = []
    for part in raw_parts:
        func_call = getattr(part, "function_call", None)
        func_resp = getattr(part, "function_response", None)
        text = getattr(part, "text", None)
        if func_call is not None:
            parts.append(
                {
                    "function_call": {
                        "id": getattr(func_call, "id", None) or "",
                        "name": getattr(func_call, "name", "tool") or "tool",
                        "args": dict(getattr(func_call, "args", None) or {}),
                    }
                }
            )
        elif func_resp is not None:
            parts.append(
                {
                    "function_response": {
                        "id": getattr(func_resp, "id", None) or "",
                        "name": getattr(func_resp, "name", "tool") or "tool",
                        "response": getattr(func_resp, "response", None),
                    }
                }
            )
        elif text:
            parts.append({"text": text})

    turn_complete = bool(getattr(event, "turn_complete", False))
    if not parts and not turn_complete:
        return None

    native: dict[str, Any] = {
        "author": getattr(event, "author", None) or "assistant",
        "content": {"parts": parts},
    }
    if getattr(event, "partial", False):
        native["partial"] = True
    if turn_complete:
        native["turn_complete"] = True
    return native
