"""End-to-end M1 contract check, fully in-process — DESIGN B (multi-framework).

Drives the REAL proxy chat route -> runtime_client -> agent-server's
framework-native event stream -> proxy translators (native / langchain /
openai-agents / google-adk) -> rich hexa SSE -> DB persistence. SQLite stands in
for Postgres; an httpx ASGITransport mounts the agent-server as the proxy's
upstream. Exercises every translator path.

Run via the platform-backend venv with the demo src dirs on PYTHONPATH.
"""

import os
import tempfile

_db = os.path.join(tempfile.gettempdir(), "hexa_e2e.sqlite")
if os.path.exists(_db):
    os.remove(_db)
os.environ["PLATFORM_DATABASE_URL"] = f"sqlite+aiosqlite:///{_db}"
from cryptography.fernet import Fernet  # noqa: E402

os.environ["PLATFORM_FERNET_KEY"] = Fernet.generate_key().decode()

import asyncio  # noqa: E402

import httpx  # noqa: E402
from agent_server.server.app import create_app as create_agent  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from platform_backend import runtime_client  # noqa: E402
from platform_backend.auth.implicit_user import seed_implicit_user  # noqa: E402
from platform_backend.db import Base, init_engine  # noqa: E402
from platform_backend.server.app import create_app as create_proxy  # noqa: E402


async def _setup():
    engine = init_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_implicit_user()


asyncio.get_event_loop().run_until_complete(_setup())

agent_app = create_agent()
runtime_client.set_client(
    httpx.AsyncClient(
        transport=httpx.ASGITransport(app=agent_app), base_url="http://agent"
    )
)
c = TestClient(create_proxy())

fail = []


def check(name, cond, extra=""):
    print(("  OK  " if cond else " FAIL ") + name + ("" if cond else f"  <- {extra}"))
    if not cond:
        fail.append(name)


def stream_message(conv_id, content):
    with c.stream("POST", f"/conversations/{conv_id}/messages",
                  json={"content": content}) as resp:
        text = b"".join(resp.iter_bytes()).decode()
    events = [
        line.split(": ", 1)[1]
        for line in text.splitlines()
        if line.startswith("event:")
    ]
    return events, text


# 1. roster + ui (NO auth header)
r = c.get("/agents")
ids = {a["id"] for a in r.json()}
check("GET /agents has 4 agents w/ main_color",
      r.status_code == 200 and {"probe", "atlas", "forge", "orbit"} <= ids
      and all(a.get("main_color") for a in r.json()), r.text[:200])
r = c.get("/agents/probe/ui")
check("GET /agents/probe/ui is text/yaml w/ main_color",
      r.status_code == 200 and r.headers["content-type"].startswith("text/yaml")
      and '#3f9d94' in r.text, f"{r.status_code}")

# 2. keys
check("PUT /me/keys/openai -> 204",
      c.put("/me/keys/openai", json={"value": "sk-test"}).status_code == 204)

# 3. per-framework: each agent's native stream normalizes to the SAME rich schema
EXPECTED = ["run_start", "block_start", "block_delta", "block_end",
            "tool_start", "tool_end", "run_end"]
FRAMEWORKS = [
    ("probe", "native", "creds-present:True"),
    ("atlas", "langchain", "LangChain echo: hello"),
    ("forge", "openai-agents", "OpenAI echo: hello"),
    ("orbit", "google-adk", "ADK echo: hello"),
]
for agent_id, fw, marker in FRAMEWORKS:
    conv_id = c.post("/conversations", json={"agent_id": agent_id}).json()["id"]
    events, text = stream_message(conv_id, "hello")
    ok_shape = all(e in events for e in EXPECTED) and events[0] == "run_start" \
        and events[-1] == "run_end"
    check(f"[{fw}] stream normalizes to run_start..block..tool..run_end",
          ok_shape, str(events))
    check(f"[{fw}] tool events carry widget=tool-calls",
          '"widget":"tool-calls"' in text, "")
    check(f"[{fw}] assistant text present ('{marker}')", marker in text, text[:300])

    msgs = c.get(f"/conversations/{conv_id}/messages").json()
    asst = next((m for m in msgs if m["role"] == "assistant"), None)
    check(f"[{fw}] persisted assistant msg w/ run_id + text",
          bool(asst and asst.get("run_id") and marker in asst["content"]),
          str(asst)[:160])

print()
if fail:
    print(f"FAILED: {fail}")
    raise SystemExit(1)
print("ALL E2E CHECKS PASSED (native + langchain + openai-agents + google-adk)")
