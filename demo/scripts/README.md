# M1 smoke checks

Executable verification of the HexaUI streaming contract (M1). Both run against
the real code — no mocks of the contract itself.

Run with a Python that has the proxy + agent-server deps (e.g. the WSL
`platform-backend/.venv`) and the demo `src` dirs on `PYTHONPATH`:

```bash
cd <repo>
PYBIN=platform-backend/.venv/bin/python
PYTHONPATH=demo/proxy/src:demo/agent-server/src:demo/packages/hexa-events/src
```

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
PYTHONPATH=demo/agent-server/src:demo/packages/hexa-events/src $PYBIN -m agent_server &   # :8080
PYTHONPATH=demo/agent-server/src:demo/packages/hexa-events/src $PYBIN demo/scripts/cancel_check.py
```

Covers: `POST /agents/{id}/cancel {run_id}` stops the run mid-stream, returns
`{cancelled: true}`, and the stream still finalizes with `run_end` (so the proxy
persists partial text).
