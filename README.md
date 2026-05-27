# Unified AI Agent Platform

A platform for building, deploying, and serving AI agents across multiple
underlying agent frameworks (LangChain, OpenAI Agents SDK, Google ADK, …)
behind a single coherent runtime protocol, event schema, and UI surface.

The platform decouples **what the agent does** (framework-native code
written by the agent author) from **how the agent runs** (isolation,
streaming, observability, configuration, UI) so that:

- agent authors keep writing idiomatic framework code;
- platform consumers (frontends, observability, the control plane) see one
  normalized event stream and one HTTP API regardless of the underlying
  framework;
- adding a new framework is one adapter, not a rewrite.

> **Status.** Runtime backend at **v0** (core, isolation, cancel API,
> three framework adapters with LangGraph/DeepAgents aliasing). Front-app
> at **slice 3 of 5** — chat E2E + per-agent UI YAML works end-to-end;
> secrets page and settings page are next. Control plane not yet built.
> See [TODO.md](TODO.md) for the full roadmap.

---

## Architecture

Two backend domains plus a UI library, deliberately separated:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Front-end (browser)                            │
│   front-app shell  ─►  custom-UI widgets (YAML-driven, SSE-aware)   │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ HTTP + SSE
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│   Platform backend (control plane)         [not yet built]          │
│   auth · RBAC · tenants · secrets · conversation persistence ·      │
│   app registry · YAML config · observability · quotas · billing     │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ HTTP
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│   Runtime backend (execution plane)                  [v0 shipped]   │
│   FastAPI + SSE  ─►  Registry  ─►  Adapter (in-process or remote)   │
│                                          │                          │
│                                          ▼                          │
│                                 Per-agent worker process            │
│                                  (own venv, own deps)               │
│                                          │                          │
│                                          ▼                          │
│                                  framework SDK (LC / OAI / ADK / …) │
└─────────────────────────────────────────────────────────────────────┘
```

The architecture mirrors modern data-plane / control-plane splits: the
runtime is stateless and horizontally scalable; the platform backend owns
all state, security, and tenant-shaped concerns.

The UI never talks framework concepts. Adapters normalize framework events
into a fixed schema (`block_delta`, `tool_start`, `state_update`,
`trace_span`, …); the UI consumes that schema. The schema is a shared
contract with the Fortify runtime — see
[backend-runtime/README.md](backend-runtime/README.md#event-schema).

For the original product spec, see [specs.md](specs.md).

---

## Repository layout

| Path | Purpose | Status |
|---|---|---|
| [backend-runtime/](backend-runtime/) | Execution plane: HTTP server, adapter framework, worker isolation, per-agent venvs. | **v0** — see its [README](backend-runtime/README.md) |
| [custom-UI/](custom-UI/) | React + TypeScript library that renders a configurable agent UI from YAML. Ships chat + `tool-calls` widgets that consume the runtime's event stream. | Library v0, chat-aware widgets live |
| [front-app/](front-app/) | User-facing app: agent picker → per-agent chat → runtime stream + cancel. Per-agent `ui.yaml` served by the runtime overrides the default chat layout. | **Slices 1–3 shipped**; see [front-app/specs.md](front-app/specs.md) |
| [specs.md](specs.md) | Original product specification. | Reference |
| [TODO.md](TODO.md) | Roadmap and milestone tracker. | Live |

---

## Quick start — full stack in two terminals

**Terminal 1 — runtime:**

```bash
cd backend-runtime
python3 -m venv .venv
.venv/bin/pip install -e '.[langchain,openai-agents,google-adk]' langchain-openai

export OPENAI_API_KEY=...
export PLATFORM_AGENTS_DIR=examples
.venv/bin/python -m platform_runtime    # listens on :8080
```

**Terminal 2 — front-app:**

```bash
cd front-app
npm install
npm run dev                              # listens on :5173
```

Open <http://localhost:5173>. The home page lists every loaded agent;
click one to chat. The LangGraph example ships a custom `ui.yaml` (three
columns: help · transcript · tool-calls panel) so you can see per-agent
layouts working.

### Bundled example agents

| Example | Framework | Needs |
|---|---|---|
| [langchain_hello](backend-runtime/examples/langchain_hello/) | LangChain (`create_agent`) | `OPENAI_API_KEY`, `langchain-openai` |
| [langgraph_hello](backend-runtime/examples/langgraph_hello/) | Bare `StateGraph` (ships custom `ui.yaml`) | `OPENAI_API_KEY`, `langchain-openai` |
| [deepagents_hello](backend-runtime/examples/deepagents_hello/) | DeepAgents | `OPENAI_API_KEY`, `langchain-openai`, `deepagents` |
| [openai_agents_hello](backend-runtime/examples/openai_agents_hello/) | OpenAI Agents SDK | `OPENAI_API_KEY` |
| [google_adk_hello](backend-runtime/examples/google_adk_hello/) | Google ADK | `GOOGLE_API_KEY` |

### Runtime-only (no UI)

For a CLI-style smoke test, hit the SSE endpoint directly:

```bash
curl -N -X POST http://127.0.0.1:8080/agents/langchain-hello/stream \
  -H 'Content-Type: application/json' \
  -d '{"input": {"messages": [{"role": "user", "content": "What time is it?"}]}}'

# Cancel an in-flight run (replace <run_id> with the run_id from the stream)
curl -X POST http://127.0.0.1:8080/agents/langchain-hello/runs/<run_id>/cancel
```

See [backend-runtime/README.md](backend-runtime/README.md) for the full
HTTP API, event schema, and adapter-authoring guide.

---

## Concepts in one minute

**Agent.** A folder with an `agent.yaml` manifest and a Python entrypoint
exposing a factory callable. The factory returns a framework-native object
(LangChain Runnable, OpenAI `Agent`, ADK `Agent`, …).

**Manifest.** Declares the framework, entrypoint, capabilities, optional
`requirements`. Validated at load time; portable; framework-agnostic
schema with an `extra` slot for framework-specific knobs.

**Adapter.** Per-framework class implementing `UnifiedAgentRuntime`.
Translates the framework's stream into the platform's normalized event
schema. Adding a new framework = writing one adapter.

**Event schema.** Typed events grouped into a Fortify-shared core
(`run_start`, `block_start`/`block_delta`/`block_end`, `tool_start`/
`tool_update`/`tool_end`, `run_end`, `error`), platform observability
extensions (`state_update`, `trace_span`), and human-in-the-loop
(`approval_requested`, `approval_resolved`). The UI and observability
layers consume events generically.

**Isolation.** Agents can run in-process (low overhead, trusted code) or
in per-agent subprocesses with their own Python venv installed from the
manifest's `requirements`. Dependency conflicts and crashes stop at the
worker boundary.

---

## Currently supported frameworks

- **LangChain ≥ 1.0** — LCEL chains, `create_agent` (LangGraph)
  outputs, bare LangGraph `StateGraph(...).compile()`, and DeepAgents
  graphs all run through one adapter. Manifests can declare
  `framework: langchain` / `langgraph` / `deepagents` — all three names
  alias to the same code path.
- **OpenAI Agents SDK ≥ 0.17** — `Runner.run_streamed` token stream
  with native tool-call mapping.
- **Google ADK ≥ 1.33** — `Runner.run_async` event stream, multi-agent
  handoff surfaces as `state_update(active_agent)`, JSON-schema-
  translated tools.

See [TODO.md](TODO.md) for upcoming frameworks (Pydantic AI).

---

## Development

Each subdirectory is independently versioned and developed.

```bash
# runtime backend
cd backend-runtime && python3 -m venv .venv && .venv/bin/pip install -e '.[langchain,openai-agents,google-adk]'
.venv/bin/python -m pytest tests/ -q

# UI library
cd custom-UI && npm install && npm test
```

The runtime backend's full test suite (34 tests, including subprocess
isolation) runs in <40s.

---

## License

TBD.
