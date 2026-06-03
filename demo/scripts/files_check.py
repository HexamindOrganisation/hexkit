"""Backend file-handling check: upload → attach to a conversation (persistent)
→ confirm the agent receives it via context.files across turns. In-process
(SQLite + ASGITransport to the agent-server), like e2e_check.py."""

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
from fastapi.testclient import TestClient  # noqa: E402

from platform_backend import runtime_client  # noqa: E402
from platform_backend.db import Base, init_engine  # noqa: E402
from platform_backend.auth.implicit_user import seed_implicit_user  # noqa: E402
from platform_backend.server.app import create_app as create_proxy  # noqa: E402
from agent_server.server.app import create_app as create_agent  # noqa: E402


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


# upload a text file (multipart)
r = c.post("/files", files={"file": ("notes.txt", b"the secret code is BANANA-42", "text/plain")})
check("POST /files -> 201 + id", r.status_code == 201 and r.json().get("id"), r.text[:200])
fid = r.json()["id"]
check("GET /files lists it", any(f["id"] == fid for f in c.get("/files").json()))

# conversation + attach
cid = c.post("/conversations", json={"agent_id": "probe"}).json()["id"]
c.post(f"/conversations/{cid}/files", json={"file_ids": [fid]})
attached = c.get(f"/conversations/{cid}/files").json()
check("attach persists on conversation", any(f["id"] == fid for f in attached), str(attached)[:200])

# turn 1: send WITHOUT file_ids — file should still be forwarded (persistent)
with c.stream("POST", f"/conversations/{cid}/messages", json={"content": "hi"}) as resp:
    t1 = b"".join(resp.iter_bytes()).decode()
check("turn-1 agent received the file (persisted, no file_ids sent)", "notes.txt" in t1, t1[-300:])

# turn 2: still there
with c.stream("POST", f"/conversations/{cid}/messages", json={"content": "again"}) as resp:
    t2 = b"".join(resp.iter_bytes()).decode()
check("turn-2 file still forwarded", "notes.txt" in t2, t2[-200:])

# detach → gone
c.delete(f"/conversations/{cid}/files/{fid}")
check("detach removes it", not any(f["id"] == fid for f in c.get(f"/conversations/{cid}/files").json()))

print()
if fail:
    print("FAILED:", fail)
    raise SystemExit(1)
print("ALL FILE CHECKS PASSED")
