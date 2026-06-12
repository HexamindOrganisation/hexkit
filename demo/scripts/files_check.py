"""Backend file-handling check: upload → attach to a conversation (persistent)
→ confirm the agent receives the file CONTENT via context.files across turns,
for both a text/plain and an application/octet-stream upload (the proxy decodes
any valid UTF-8 regardless of mime). In-process (SQLite + ASGITransport)."""

import os
import tempfile

_db = os.path.join(tempfile.gettempdir(), "hexa_files.sqlite")
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
runtime_client.set_client(
    httpx.AsyncClient(transport=httpx.ASGITransport(app=create_agent()), base_url="http://a")
)
c = TestClient(create_proxy())
fail = []


def check(name, cond, extra=""):
    print(("  OK  " if cond else " FAIL ") + name + ("" if cond else f"  <- {extra}"))
    if not cond:
        fail.append(name)


def send(cid, content):
    """Send a turn, then return the persisted assistant reply (NOT the raw
    stream — that includes run_start.input = history, which would carry prior
    turns' echoed file content and mask detach)."""
    with c.stream("POST", f"/conversations/{cid}/messages", json={"content": content}) as r:
        for _ in r.iter_bytes():
            pass
    msgs = c.get(f"/conversations/{cid}/messages").json()
    replies = [m["content"] for m in msgs if m["role"] == "assistant"]
    return replies[-1] if replies else ""


# Upload two files: a normal text/plain, and one mislabeled octet-stream.
txt = c.post("/files", files={"file": ("identity.txt", b"name: Quentin; secret BANANA-42", "text/plain")}).json()
binlabeled = c.post(
    "/files",
    files={"file": ("report.log", b"bug ZEBRA-99 on startup", "application/octet-stream")},
).json()
check("two uploads created", bool(txt.get("id") and binlabeled.get("id")))

cid = c.post("/conversations", json={"agent_id": "probe"}).json()["id"]
c.post(f"/conversations/{cid}/files", json={"file_ids": [txt["id"], binlabeled["id"]]})

t1 = send(cid, "what do you know about me?")
check("text/plain CONTENT reached agent (BANANA-42)", "BANANA-42" in t1, t1[-400:])
check("octet-stream CONTENT decoded + reached agent (ZEBRA-99)", "ZEBRA-99" in t1, t1[-400:])

# Persists across turns without re-sending file_ids.
t2 = send(cid, "again?")
check("content still forwarded on turn 2", "BANANA-42" in t2 and "ZEBRA-99" in t2, t2[-300:])

# Detach one → its content stops being forwarded on the next turn.
c.delete(f"/conversations/{cid}/files/{txt['id']}")
t3 = send(cid, "and now?")
check("detached file no longer sent", "BANANA-42" not in t3 and "ZEBRA-99" in t3, t3)

print()
if fail:
    print("FAILED:", fail)
    raise SystemExit(1)
print("ALL FILE CONTENT CHECKS PASSED")
