"""
Per-agent actions: manifest declares functions in `actions.py`; the
runtime exposes them at `POST /agents/{id}/actions/{name}`. Side-effect
events bundled with the action's result get re-emitted to widget inboxes
by the front-end (not tested here — that's a JS-side concern).

Covers in-process and subprocess isolation.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Activate the LangChain adapter so manifests using `framework: langchain`
# resolve in the in-process tests. The subprocess worker already imports it.
from platform_runtime.adapters import langchain_adapter  # noqa: F401
from platform_runtime.actions import (
    ActionError,
    LocalActionHost,
    load_action_callables,
)
from platform_runtime.manifest import load_manifest
from platform_runtime.registry import AgentRegistry, IsolationMode
from platform_runtime.server import create_app


# ---------------------------------------------------------------------------
# Helpers — build a tiny fake-framework agent that declares two actions.
# ---------------------------------------------------------------------------

def _write_agent_with_actions(tmp_path: Path) -> Path:
    """Materialize an agent folder with two actions and return its path.

    Uses `framework: langchain` with a trivial `RunnableLambda` so the
    agent loads in both in-process and subprocess mode (the subprocess
    worker doesn't know about the test-only `fake` framework, but it
    does have the LangChain adapter built in).
    """
    agent_dir = tmp_path / "actions-agent"
    agent_dir.mkdir()
    (agent_dir / "agent.yaml").write_text(
        textwrap.dedent(
            """
            agent_id: actions-agent
            name: Actions Agent
            framework: langchain
            entrypoint: agent.py
            agent_callable: build_agent
            actions:
              - echo
              - publish_to_widget
            """
        ).lstrip()
    )
    (agent_dir / "agent.py").write_text(
        textwrap.dedent(
            """
            from langchain_core.runnables import RunnableLambda
            def build_agent():
                return RunnableLambda(lambda x: x)
            """
        ).lstrip()
    )
    (agent_dir / "actions.py").write_text(
        textwrap.dedent(
            '''
            async def echo(args, *, context):
                """Round-trips args back as the result. No side effects."""
                return {"echoed": args}

            def publish_to_widget(args, *, context):
                """Emits one widget update; result is just a marker."""
                context.emit(
                    widget="my-widget",
                    payload={"hello": args.get("name", "world")},
                )
                return {"emitted": True}
            '''
        ).lstrip()
    )
    return agent_dir


# ---------------------------------------------------------------------------
# Unit tests for the action loader + LocalActionHost
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_local_action_invocation(tmp_path: Path) -> None:
    agent_dir = _write_agent_with_actions(tmp_path)
    manifest, root = load_manifest(agent_dir)
    callables = load_action_callables(manifest, root)
    host = LocalActionHost(declared=manifest.actions, callables=callables)

    assert host.declared == ["echo", "publish_to_widget"]
    out = await host.invoke("echo", {"x": 1})
    assert out.result == {"echoed": {"x": 1}}
    assert out.events == []


@pytest.mark.asyncio
async def test_local_action_emits_widget_events(tmp_path: Path) -> None:
    agent_dir = _write_agent_with_actions(tmp_path)
    manifest, root = load_manifest(agent_dir)
    host = LocalActionHost(
        declared=manifest.actions,
        callables=load_action_callables(manifest, root),
    )
    out = await host.invoke("publish_to_widget", {"name": "ada"})
    assert out.result == {"emitted": True}
    assert len(out.events) == 1
    assert out.events[0].widget == "my-widget"
    assert out.events[0].payload == {"hello": "ada"}


@pytest.mark.asyncio
async def test_local_action_unknown_name_raises(tmp_path: Path) -> None:
    agent_dir = _write_agent_with_actions(tmp_path)
    manifest, root = load_manifest(agent_dir)
    host = LocalActionHost(
        declared=manifest.actions,
        callables=load_action_callables(manifest, root),
    )
    with pytest.raises(ActionError, match="Unknown action"):
        await host.invoke("not_a_real_action", {})


def test_missing_actions_file_when_declared(tmp_path: Path) -> None:
    agent_dir = tmp_path / "broken"
    agent_dir.mkdir()
    (agent_dir / "agent.yaml").write_text(
        textwrap.dedent(
            """
            agent_id: broken
            name: Broken
            framework: fake
            entrypoint: agent.py
            agent_callable: build_agent
            actions: [foo]
            """
        ).lstrip()
    )
    (agent_dir / "agent.py").write_text("def build_agent(): return []\n")
    manifest, root = load_manifest(agent_dir)
    with pytest.raises(ActionError, match="does not exist"):
        load_action_callables(manifest, root)


# ---------------------------------------------------------------------------
# HTTP route tests (in-process)
# ---------------------------------------------------------------------------

@pytest.fixture
def actions_client(tmp_path: Path) -> TestClient:
    agent_dir = _write_agent_with_actions(tmp_path)
    reg = AgentRegistry()
    reg.load(agent_dir)
    return TestClient(create_app(reg))


def test_action_endpoint_returns_envelope(actions_client: TestClient) -> None:
    r = actions_client.post(
        "/agents/actions-agent/actions/echo",
        json={"args": {"x": 1}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["result"] == {"echoed": {"x": 1}}
    assert body["events"] == []


def test_action_endpoint_returns_side_effect_events(
    actions_client: TestClient,
) -> None:
    r = actions_client.post(
        "/agents/actions-agent/actions/publish_to_widget",
        json={"args": {"name": "linus"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["result"] == {"emitted": True}
    assert body["events"] == [
        {"widget": "my-widget", "payload": {"hello": "linus"}}
    ]


def test_unknown_action_is_404(actions_client: TestClient) -> None:
    r = actions_client.post(
        "/agents/actions-agent/actions/no_such_thing",
        json={"args": {}},
    )
    assert r.status_code == 404


def test_unknown_agent_is_404(actions_client: TestClient) -> None:
    r = actions_client.post(
        "/agents/does-not-exist/actions/echo",
        json={"args": {}},
    )
    assert r.status_code == 404


def test_agent_with_no_actions_is_404(
    actions_client: TestClient, fake_agent_dir: Path
) -> None:
    """The conftest's `fake_agent_dir` declares no actions.

    Loading it alongside the actions-agent agent and posting an action to
    it should 404 — not 405 or 500 — because the agent doesn't expose
    any actions, regardless of the route shape."""
    # Need a fresh registry with the no-actions agent loaded.
    reg = AgentRegistry()
    reg.load(fake_agent_dir)
    with TestClient(create_app(reg)) as client:
        r = client.post("/agents/my-fake/actions/foo", json={"args": {}})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Subprocess isolation
# ---------------------------------------------------------------------------

@pytest.mark.subprocess
def test_action_round_trips_through_worker(tmp_path: Path) -> None:
    """Spawn a real worker, hit the action endpoint, verify the round-trip
    came back with the same envelope."""
    agent_dir = _write_agent_with_actions(tmp_path)
    reg = AgentRegistry(isolation=IsolationMode.SUBPROCESS)
    reg.load(agent_dir)
    with TestClient(create_app(reg)) as client:
        r = client.post(
            "/agents/actions-agent/actions/publish_to_widget",
            json={"args": {"name": "grace"}},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["result"] == {"emitted": True}
        assert body["events"] == [
            {"widget": "my-widget", "payload": {"hello": "grace"}}
        ]
