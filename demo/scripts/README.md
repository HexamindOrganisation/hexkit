# M1 smoke checks

Executable verification of the HexaUI streaming contract (M1). Both run against
the real code — no mocks of the contract itself.

First-time setup (creates the venvs from the pyprojects; needs [`uv`](https://docs.astral.sh/uv/)):

```bash
bash demo/scripts/setup.sh
```

Run with a Python that has the proxy deps (the WSL `demo/proxy/.venv`) and the
demo `src` dirs on `PYTHONPATH`:

```bash
cd <repo>
PYBIN=demo/proxy/.venv/bin/python
PYTHONPATH=demo/proxy/src:demo/agent-server/src:demo/packages/hexa-events/src
```

## `verify_backend.py` — conformance checker for *your* backend (live URL)

The integrator-facing tool. Unlike the in-process checks below, this hits a
**running** backend over a real socket — yours, or the bundled reference — and
validates the [CONTRACT.md §8](../CONTRACT.md) checklist the way the proxy
would: it assigns a `run_id`, reads the SSE stream, cancels mid-run, and
inspects every frame's shape (`{framework, event}`, supported framework, native
event vocabulary, `{cancelled: bool}`, `{result}`). Prints PASS/FAIL/SKIP per
item and exits non-zero on any failure, so it works as a CI gate.

Only needs `httpx` (in every demo venv). Start a backend, then:

```bash
$PYBIN demo/scripts/verify_backend.py http://127.0.0.1:9080            # first roster agent
$PYBIN demo/scripts/verify_backend.py http://127.0.0.1:9080 --agent orbit
```

Pairs with [`../starter-agent/`](../starter-agent/), the minimal copy-me backend
this checker is the acceptance test for.

## `e2e_check.py` — full contract path, in-process (all frameworks)

Drives the **real** proxy chat route → `runtime_client` → agent-server's
**framework-native** event stream → the matching proxy translator (`native` /
`langchain` / `openai-agents` / `google-adk`) → rich hexa SSE → DB persistence.
SQLite stands in for Postgres; an httpx `ASGITransport` mounts the agent-server
as the proxy's upstream. No servers to start.

```bash
PYTHONPATH=$PYTHONPATH $PYBIN demo/scripts/e2e_check.py
```

Covers, **for each of the 4 framework agents** (probe/atlas/forge/orbit): roster
+ `main_color`, `ui.yaml`, set keys, create conversation, that the native stream
normalizes to the same rich schema (`run_start`…`block`…`tool`…`run_end`), tool
events carry `widget="tool-calls"`, the framework's text marker appears, and the
assistant message persists with `run_id`.

## `cancel_check.py` — mid-stream cancel, live socket

`ASGITransport` buffers the whole response, so cancel must be tested over a real
connection. It hits the agent-server directly (which speaks the minimal format),
so it parses `data:` JSON `type` fields. Start the agent-server first, then run:

```bash
PYTHONPATH=demo/agent-server/src:demo/packages/hexa-events/src $PYBIN -m agent_server &   # :9080
PYTHONPATH=demo/agent-server/src:demo/packages/hexa-events/src $PYBIN demo/scripts/cancel_check.py
```

Covers: `POST /agents/{id}/cancel {run_id}` stops the run mid-stream, returns
`{cancelled: true}`, and the stream still finalizes with `run_end` (so the proxy
persists partial text).

## `files_check.py` — attachments reach the (echo) agent

Upload → attach to a conversation → confirm `context.files` content reaches the
agent across turns (text/plain **and** mislabeled `application/octet-stream`,
which the proxy decodes as UTF-8), and that detaching stops forwarding it.
In-process; asserts on the **persisted** assistant reply.

```bash
PYTHONPATH=$PYTHONPATH $PYBIN demo/scripts/files_check.py
```

## `llm_files_check.py` — attachments reach the **model**

Goes one layer deeper than `files_check.py`: exercises the OpenAI-backed
`LLMAgent` and captures the exact `messages` array handed to
`chat.completions.create`, asserting the file content was inlined into the
model's context. A **fake** `openai` module is injected (no key, no network), so
this is deterministic and free. Diagnoses the common "the LLM says it can't see
my file" symptom — each failed check prints the likely cause (LLM not selected /
key not forwarded / mime dropped / call degraded to the error fallback), and it
prints the messages the model actually received.

```bash
PYTHONPATH=$PYTHONPATH $PYBIN demo/scripts/llm_files_check.py
```
