# HexaUI

A **UI/UX-first multi-agent chat platform**. Developers bring their own
streaming agent backend (any framework); HexaUI provides the chat experience —
a configurable, YAML-driven UI, conversation history, folders, file attachments,
encrypted secrets — and a thin proxy that normalizes any framework's event
stream into one schema the UI renders.

> **The pivot.** This repo began as a *unified agent runtime* (a backend that
> wrapped LangChain/OpenAI/Google-ADK behind one protocol). That product was
> dropped. HexaUI keeps the good parts — the event schema + the YAML widget
> library — and refocuses on the **UI and the developer contract**. The old
> runtime lives in [`legacy/`](legacy/) for reference only.

Core design principle: **the active agent's color is the only color in the
product**, driven from a single variable (`page.main_color` → `--accent`).

---

## How it fits together

```
┌───────────────────────────────────────────────────────────────┐
│  front-app (React/Vite shell)                                 │
│   folding sidebar · agent picker · composer                   │
│   └─ mounts custom-UI <AgentUI>, rendered from the agent's    │
│      ui.yaml (widgets + theme)                                │
└───────────────────────────────┬───────────────────────────────┘
                                │ HTTP + SSE  (single origin)
                                ▼
┌───────────────────────────────────────────────────────────────┐
│  demo/proxy  (FastAPI)                                        │
│   JWT auth (argon2id) · conversations · folders · files       │
│   · Fernet-encrypted per-user keys · per-framework            │
│   translators normalize native events → hexa SSE schema       │
└───────────────────────────────┬───────────────────────────────┘
                                │ HTTP + SSE  (the developer contract)
                                ▼
┌───────────────────────────────────────────────────────────────┐
│  demo/agent-server  (reference developer backend)             │
│   each agent declares a `framework` and forwards that         │
│   framework's NATIVE events, tagged. You replace this with    │
│   your own backend (CONTRACT.md).                             │
└───────────────────────────────────────────────────────────────┘
```

The developer never reshapes their events into our schema and never writes UI
code: they implement five HTTP endpoints and forward their framework's native
events; the **proxy translates** and the **UI renders from YAML**. See
[demo/CONTRACT.md](demo/CONTRACT.md).

---

## Repository layout

| Path | Purpose |
|---|---|
| [custom-UI/](custom-UI/) | The product's heart: a React + TS library that renders a configurable agent UI from YAML (`<AgentUI>` + 11 built-in widgets). Theme bridge, streaming chat, the actions/`data_source` system. |
| [demo/](demo/) | The runnable reference stack: [`proxy/`](demo/proxy/) (platform backend), [`agent-server/`](demo/agent-server/) (a contract-conformant developer backend with 6 sample agents), [`hexgate-agent/`](demo/hexgate-agent/) (a standalone hexgate-wrapped backend), [`starter-agent/`](demo/starter-agent/) (a minimal **copy-me** backend — the whole contract in one file), [`packages/hexa-events/`](demo/packages/hexa-events/) (the internal event schema), [`scripts/`](demo/scripts/) (run + smoke checks, incl. the `verify_backend.py` conformance CLI). |
| [front-app/](front-app/) | The HexaUI shell that consumes `custom-UI` and talks to the proxy. |
| [legacy/](legacy/) | The dropped unified-runtime backend (`backend-runtime`), kept for reference. Not part of the live product. |
| [demo/CONTRACT.md](demo/CONTRACT.md) | The developer contract — the one document an integrator reads. |

---

## Quick start

**Prerequisites:** [`uv`](https://docs.astral.sh/uv/) and Node.js 18+.

```bash
make setup        # one-time: Python venvs + custom-UI build + front-app npm install
make dev          # backends + frontend together; Ctrl-C tears down both
```

Open <http://localhost:8873>. The app redirects to **`/login`**. Sign in as
one of the demo accounts (all share the password `hexademo`):

- `dev01@hexamind.ai` (admin)
- `alice@example.com` (billing)
- `bob@example.com` (support)
- `carol@example.com` (no role)

Or sign up a fresh account at `/signup`. The demo accounts come from
[`demo-users.yaml`](demo-users.yaml), upserted on startup when
`PLATFORM_DEMO_USERS_FILE` is set (set by default in `make dev`).

To get real model replies rather than the deterministic echo/canned fallback,
set your provider key in **Settings** (OpenAI for Probe, Google for Orbit) —
the proxy forwards it to the agent backend per run, never persisting it in
plaintext. The same Settings page has a free-text `role` field; if you point
HexUI at a `hexgate`-wrapped agent, that role is forwarded to the agent and
drives hexgate's per-tool policy + audit pipeline.

Run `make help` to see all targets (`test`, `lint`, `typecheck`, …). The full
guide with troubleshooting and configuration is in [QUICKSTART.md](QUICKSTART.md);
suggested next steps for the project live in [IMPROVEMENTS.md](IMPROVEMENTS.md).

The bundled agents demonstrate the contract end to end:

| Agent | Framework | Showcases |
|---|---|---|
| **Probe** | `native` (OpenAI) | the simple real-LLM chat |
| **Orbit** | `google-adk` (Gemini) | a real LLM **plus** the widget actions + `data_source` workspace |
| **Atlas** | `langchain` | the LangChain translator (canned native events) |
| **Forge** | `openai-agents` | the OpenAI Agents translator (canned native events) |
| **Healthcare** | `openai-agents` (OpenAI) | a real clinical-assistant agent; HexGate-gated when `HEXGATE_KEY` is set, scoping per-tool policy to the caller's `context.user` role |
| **DevOps** | `google-adk` (OpenAI via LiteLLM) | a real infra-assistant agent; HexGate-gated when `HEXGATE_KEY` is set, scoping per-tool policy to the caller's `context.user` role |
| **Hexgate Guard** | `hexgate` | a hexgate-wrapped agent that opens `User(user_id, role)` per run and emits audit decisions to the hexgate cloud (separate backend at [`demo/hexgate-agent/`](demo/hexgate-agent/)) |

---

## The two things a developer configures

1. **`ui.yaml`** — which widgets, where, and the accent color. Placed/served by
   the developer backend (`GET /agents/{id}/ui`).
2. **A backend** conforming to [demo/CONTRACT.md](demo/CONTRACT.md): five
   endpoints; stream framework-native events tagged `{framework, event}`.

Beyond the chat turn (which the platform owns), widget behavior is just two
declarative primitives — **`action`** (do something → `POST /actions/{name}`)
and **`data_source`** (display something, refreshed by re-pull). The backend
stays UI-agnostic; the YAML is the only wiring layer. See CONTRACT §5b.

### Build your own backend

The fastest path: copy [`demo/starter-agent/`](demo/starter-agent/) — the entire
contract in one annotated file (one `native` echo agent, the five endpoints,
one `ui.yaml`) — and change the three spots marked `# CHANGE ME`. Then validate
it against any running URL:

```bash
# Acts as the proxy would: assigns a run_id, reads the SSE stream, cancels
# mid-run, checks every frame's shape against CONTRACT.md §8. Exits non-zero
# on failure, so it works as a CI gate too.
python demo/scripts/verify_backend.py http://127.0.0.1:8880
```

[`demo/agent-server/`](demo/agent-server/) is the richer reference (every
framework + the actions/`data_source` workspace); the starter is the opposite —
the fewest moving parts that still pass conformance.

---

## Development

The top-level [Makefile](Makefile) wraps the most common loops:

```bash
make test         # proxy test suite
make lint         # ruff check across every Python package (shared ruff.toml)
make format       # ruff format across every Python package
make typecheck    # tsc --noEmit on custom-UI and front-app
make check        # lint + test + typecheck — the same gates CI enforces
make clean        # wipe venvs and node_modules
```

CI runs the same gates on every push and PR — see
[.github/workflows/ci.yml](.github/workflows/ci.yml).

For lower-level work directly against the packages:

```bash
# UI library (the core)
cd custom-UI && npm install && npm test && npm run build

# Web app
cd front-app && npm install && npx tsc --noEmit && npx vite build

# Backend contract smoke checks
PYTHONPATH=demo/proxy/src:demo/agent-server/src:demo/packages/hexa-events/src \
  demo/proxy/.venv/bin/python demo/scripts/e2e_check.py
```

See [demo/scripts/README.md](demo/scripts/README.md) for all smoke checks and
[custom-UI/docs/](custom-UI/docs/) for the widget catalog and YAML reference.

---

## License

TBD.
