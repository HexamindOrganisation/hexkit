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
│  demo/proxy  (FastAPI · single-user)                          │
│   auth-less implicit user · conversations · folders · files   │
│   · Fernet-encrypted keys · per-framework translators that    │
│   normalize native events → the rich hexa SSE schema          │
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
| [demo/](demo/) | The runnable reference stack: [`proxy/`](demo/proxy/) (platform backend), [`agent-server/`](demo/agent-server/) (a contract-conformant developer backend with 4 sample agents), [`starter-agent/`](demo/starter-agent/) (a minimal **copy-me** backend — the whole contract in one file), [`packages/hexa-events/`](demo/packages/hexa-events/) (the internal event schema), [`scripts/`](demo/scripts/) (run + smoke checks, incl. the `verify_backend.py` conformance CLI). |
| [front-app/](front-app/) | The HexaUI shell that consumes `custom-UI` and talks to the proxy. |
| [legacy/](legacy/) | The dropped unified-runtime backend (`backend-runtime`), kept for reference. Not part of the live product. |
| [demo/CONTRACT.md](demo/CONTRACT.md) | The developer contract — the one document an integrator reads. |
| [demo/HANDOFF.md](demo/HANDOFF.md) | Implementation handoff / architecture notes. |

---

## Quick start

Two backends (proxy + agent-server) on a throwaway SQLite DB, plus the web app.

```bash
# One-time — create the backend venvs from their pyprojects (needs `uv`).
bash demo/scripts/setup.sh

# Terminal 1 — backends (WSL). Set AGENT_ENABLE_LLM=1 for real LLM replies.
AGENT_ENABLE_LLM=1 bash demo/scripts/run-backends.sh    # agent-server :8880, proxy :8800

# Terminal 2 — web app
cd front-app && npm install && npm run dev               # http://localhost:8873
```

Open <http://localhost:8873>, pick an agent, and chat. To get real model replies
rather than the deterministic echo/canned fallback, set your provider key in
**Settings** (OpenAI for Probe, Google for Orbit) — the proxy forwards it to the
agent backend per run, never persisting it in plaintext.

The bundled agents demonstrate the contract end to end:

| Agent | Framework | Showcases |
|---|---|---|
| **Probe** | `native` (OpenAI) | the simple real-LLM chat |
| **Orbit** | `google-adk` (Gemini) | a real LLM **plus** the widget actions + `data_source` workspace |
| **Atlas** | `langchain` | the LangChain translator (canned native events) |
| **Forge** | `openai-agents` | the OpenAI Agents translator (canned native events) |

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

```bash
# UI library (the core)
cd custom-UI && npm install && npm test && npm run build

# Web app
cd front-app && npm install && npx tsc --noEmit && npx vite build

# Backend contract smoke checks (WSL; venvs live in demo/proxy + demo/agent-server)
PYTHONPATH=demo/proxy/src:demo/agent-server/src:demo/packages/hexa-events/src \
  demo/proxy/.venv/bin/python demo/scripts/e2e_check.py
```

See [demo/scripts/README.md](demo/scripts/README.md) for all smoke checks and
[custom-UI/docs/](custom-UI/docs/) for the widget catalog and YAML reference.

---

## License

TBD.
