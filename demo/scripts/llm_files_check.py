"""LLM file-context check: prove that attached files actually reach the *model*.

`files_check.py` proves the proxy forwards `context.files` to the (echo) agent.
This one goes one layer deeper — it exercises the OpenAI-backed `LLMAgent` and
captures the exact `messages` array handed to `chat.completions.create`, so we
can assert the file content was inlined into the model's context.

To stay deterministic (no key, no network, no cost) we inject a FAKE `openai`
module before the run: it records the `messages` + `api_key` it's called with
and streams back a sentinel reply. So this validates the wiring end-to-end:

    upload → attach → proxy decrypts key + forwards files
        → select_agent picks LLMAgent → LLMAgent inlines files into messages
        → tokens stream back → proxy persists the reply

In-process (SQLite + ASGITransport). Run:  python scripts/llm_files_check.py

If a check FAILS, the most likely real-world cause is printed next to it.
"""

import os
import sys
import tempfile
import types

# --- env BEFORE importing the apps -----------------------------------------
_db = os.path.join(tempfile.gettempdir(), "hexa_llm_files.sqlite")
if os.path.exists(_db):
    os.remove(_db)
os.environ["PLATFORM_DATABASE_URL"] = f"sqlite+aiosqlite:///{_db}"
os.environ["AGENT_ENABLE_LLM"] = "1"  # so select_agent can choose LLMAgent

from cryptography.fernet import Fernet  # noqa: E402

os.environ["PLATFORM_FERNET_KEY"] = Fernet.generate_key().decode()


# --- fake `openai` module: capture what the model is asked --------------------
# `LLMAgent.run` does `from openai import AsyncOpenAI` lazily, so injecting this
# into sys.modules now makes the agent use our stub instead of the real client.
_captured: dict = {}


class _Delta:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.delta = _Delta(content)


class _Chunk:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _FakeCompletions:
    async def create(self, *, model, messages, stream, **kw):
        _captured["model"] = model
        _captured["messages"] = messages
        _captured["stream"] = stream

        async def _gen():
            for tok in ["FAKE_LLM_OK", " ", "reply"]:
                yield _Chunk(tok)

        return _gen()


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class _FakeAsyncOpenAI:
    def __init__(self, api_key=None, **kw):
        _captured["api_key"] = api_key
        self.chat = _FakeChat()


_fake_openai = types.ModuleType("openai")
_fake_openai.AsyncOpenAI = _FakeAsyncOpenAI
sys.modules["openai"] = _fake_openai


# --- wire the in-process stack ----------------------------------------------
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


def check(name, cond, why=""):
    print(("  OK  " if cond else " FAIL ") + name + ("" if cond else f"\n        ↳ {why}"))
    if not cond:
        fail.append(name)


def send(cid, content):
    with c.stream("POST", f"/conversations/{cid}/messages", json={"content": content}) as r:
        for _ in r.iter_bytes():
            pass
    msgs = c.get(f"/conversations/{cid}/messages").json()
    replies = [m["content"] for m in msgs if m["role"] == "assistant"]
    return replies[-1] if replies else ""


# --- the scenario -----------------------------------------------------------
# Store an OpenAI key (the proxy decrypts + forwards it as a credential, which is
# what makes select_agent pick LLMAgent over EchoAgent).
r = c.put("/me/keys/openai", json={"value": "sk-test-CAFEBABE"})
check("openai key stored (PUT /me/keys/openai)", r.status_code in (200, 204), f"HTTP {r.status_code}: {r.text}")

# Two files: a normal text/plain and one mislabeled application/octet-stream
# (browsers do this). Each carries a unique marker we can search for.
txt = c.post(
    "/files",
    files={"file": ("brief.txt", b"Internal: PROJECT NEPTUNE launch code is BANANA-42.", "text/plain")},
).json()
binlabeled = c.post(
    "/files",
    files={"file": ("notes.log", b"Reminder: vault password is ZEBRA-99.", "application/octet-stream")},
).json()
# A genuinely binary file (invalid UTF-8, like a real PDF/image/docx). The
# ASCII marker is visible in the raw bytes but the file does NOT decode, so it
# must come through as content=null → "[binary file omitted]".
pdf = c.post(
    "/files",
    files={"file": ("brief.pdf", b"%PDF-1.4 SECRET_PDF_MARKER \xff\xfe\x00 stream", "application/pdf")},
).json()
check("three uploads created", bool(txt.get("id") and binlabeled.get("id") and pdf.get("id")))

cid = c.post("/conversations", json={"agent_id": "probe"}).json()["id"]
c.post(f"/conversations/{cid}/files", json={"file_ids": [txt["id"], binlabeled["id"], pdf["id"]]})

reply = send(cid, "What is the launch code?")

# --- assertions: did the file content reach the MODEL? ----------------------
msgs = _captured.get("messages")

check(
    "LLMAgent was selected (model was actually called)",
    msgs is not None,
    "create() never ran → EchoAgent answered, not the LLM. Check AGENT_ENABLE_LLM=1 "
    "and that an openai_api_key is forwarded (key stored for THIS user).",
)
check(
    "forwarded openai key reached the agent",
    _captured.get("api_key") == "sk-test-CAFEBABE",
    f"agent saw api_key={_captured.get('api_key')!r} — credential decrypt/forward broke.",
)

system_blob = "\n".join(
    str(m.get("content", "")) for m in (msgs or []) if m.get("role") == "system"
)
check(
    "text/plain file content inlined into model context (PROJECT NEPTUNE)",
    "PROJECT NEPTUNE" in system_blob,
    "the file's text never made it into the messages sent to the model.",
)
check(
    "octet-stream file content decoded + inlined (ZEBRA-99)",
    "ZEBRA-99" in system_blob,
    "non-text/* mime dropped — the proxy should decode any valid UTF-8 (see chat._decode_text).",
)
check(
    "user question reached the model",
    any("launch code" in str(m.get("content", "")) for m in (msgs or []) if m.get("role") == "user"),
    "history assembly didn't include the user turn.",
)
check(
    "binary file (PDF) comes through as [binary file omitted], NOT its bytes",
    "[binary file omitted]" in system_blob and "SECRET_PDF_MARKER" not in system_blob,
    "THIS is the usual 'the model ignores my file' cause: PDFs/images/docx aren't "
    "valid UTF-8, so content=null and the model only sees the placeholder. "
    "Extract text upstream or send a provider file/vision block.",
)
check(
    "model reply streamed back through the proxy (FAKE_LLM_OK)",
    "FAKE_LLM_OK" in reply,
    f"persisted reply was: {reply!r}",
)
check(
    "LLM call did NOT degrade to the error fallback",
    "[llm unavailable" not in reply,
    f"the openai call threw and was swallowed; reply: {reply!r}",
)

# --- show exactly what the model received (the debugging payoff) ------------
print("\n--- messages handed to the model (truncated) ---")
for m in msgs or []:
    body = str(m.get("content", "")).replace("\n", " ")
    print(f"  [{m.get('role')}] {body[:120]}")

print()
if fail:
    print("FAILED:", fail)
    raise SystemExit(1)
print("ALL LLM FILE-CONTEXT CHECKS PASSED")
