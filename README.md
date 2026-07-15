<div align="center">

<img src="assets/hexkit-mark.svg" width="72" height="72" alt="HexKit">

# HexKit

</div>

A **UI/UX-first multi-agent chat platform**. Developers bring their own
streaming agent backend (any framework); HexKit provides the chat experience —
a configurable, YAML-driven UI, conversation history, folders, file attachments
— and a thin proxy that normalizes any framework's event stream into one schema
the UI renders.

<p align="center">
  <img src="assets/hero.png" alt="HexKit — the DevOps agent: a YAML-driven dashboard (service metrics + table) above a streaming chat, themed by the active agent's accent color." width="100%">
</p>

<p align="center">
  <a href="https://github.com/HexamindOrganisation/hexkit/actions/workflows/ci.yml"><img src="https://github.com/HexamindOrganisation/hexkit/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/node-18+-339933?logo=node.js&logoColor=white" alt="Node 18+">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
</p>

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
│  proxy-server  (FastAPI)                                      │
│   JWT auth (argon2id) · conversations · folders · files       │
│   · per-framework translators normalize native events →       │
│   hexa SSE schema                                             │
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
[CONTRACT.md](CONTRACT.md).

---

## Repository layout

| Path | Purpose |
|---|---|
| [custom-UI/](custom-UI/) | The product's heart: a React + TS library that renders a configurable agent UI from YAML (`<AgentUI>` + 12 built-in widgets). Theme bridge, streaming chat, the actions/`data_source` system. |
| [front-app/](front-app/) | The HexKit shell that consumes `custom-UI` and talks to the proxy. |
| [proxy-server/](proxy-server/) | The platform backend (FastAPI): JWT auth, conversations, folders, files, and the per-framework translators that normalize native events into the hexa SSE schema. Import package stays `platform_backend`. |
| [packages/hexa-events/](packages/hexa-events/) | The internal event schema package consumed by the proxy (a local path dependency). |
| [demo/](demo/) | The runnable reference backends: [`agent-server/`](demo/agent-server/) (a contract-conformant developer backend with 8 sample agents — Probe, Orbit, Atlas, Forge, Healthcare, DevOps, ITSM, HR), [`hexgate-agent/`](demo/hexgate-agent/) (a standalone hexgate-wrapped backend), [`starter-agent/`](demo/starter-agent/) (a minimal **copy-me** backend — the whole contract in one file), and [`scripts/`](demo/scripts/) (run + smoke checks, incl. the `verify_backend.py` conformance CLI). |
| [legacy/](legacy/) | The dropped unified-runtime backend (`backend-runtime`), kept for reference. Not part of the live product. |
| [CONTRACT.md](CONTRACT.md) | The developer contract — the one document an integrator reads. |

---

## Quick start

**Prerequisites:** [`uv`](https://docs.astral.sh/uv/) and Node.js 18+.

```bash
make setup        # one-time: Python venvs + custom-UI build + front-app npm install
make dev          # backends + frontend together; Ctrl-C tears down both
```

Open <http://localhost:8873>. The app redirects to **`/login`**. Sign in as
one of the demo accounts (all share the password `hexademo`):

- `guest@example.com` (no role — exercises the fail-closed `default`)
- `vince@hexamind.ai` (viewer), `olivia@hexamind.ai` (operator), `aaron@hexamind.ai` (admin) — devops roles
- `nadia@clinic.org` (nurse), `priya@clinic.org` (physician), `bianca@clinic.org` (billing_staff) — healthcare roles

The `role` only changes behavior when an agent is HexGate-gated (healthcare /
devops with `HEXGATE_API_KEY` set); it scopes that agent's per-tool policy.

Or sign up a fresh account at `/signup`. The demo accounts come from
[`demo-users.yaml`](demo-users.yaml), upserted on startup when
`PLATFORM_DEMO_USERS_FILE` is set (set by default in `make dev`).

To get real model replies rather than the deterministic echo/canned fallback,
put your provider keys in the **agent backend's environment** (`OPENAI_API_KEY`
for Probe + the healthcare/devops agents, `GOOGLE_API_KEY` for Orbit) and start
it with `AGENT_ENABLE_LLM=1` — see [`demo/agent-server/.env.sample`](demo/agent-server/.env.sample).
HexKit never holds your model keys. The **Settings** page carries only your
display name and a free-text `role`; if you point HexKit at a `hexgate`-wrapped
agent, that role is forwarded to the agent and drives hexgate's per-tool policy
+ audit pipeline.

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
| **Healthcare** | `openai-agents` (OpenAI) | a real clinical-assistant agent; HexGate-gated when `HEXGATE_API_KEY` is set, scoping per-tool policy to the caller's `context.user` role |
| **DevOps** | `google-adk` (OpenAI via LiteLLM) | a real infra-assistant agent; HexGate-gated when `HEXGATE_API_KEY` is set, scoping per-tool policy to the caller's `context.user` role |
| **ITSM** | `langchain` (deepagents) | a change-request assistant with a live lifecycle dashboard (refresh button → funnel metrics + change table updates as the agent's tools run) |
| **HR** | `langchain` (deepagents) | an internal HR assistant; demonstrates stateful per-user data (`hr_state.py`) and role-gated tools when HexGate is wired |
| **Hexgate Guard** | `hexgate` | a hexgate-wrapped agent that opens `User(user_id, role)` per run and emits audit decisions to the hexgate cloud (separate backend at [`demo/hexgate-agent/`](demo/hexgate-agent/)) |

---

## Components

Every agent UI is built out of these widgets. You compose them in a `ui.yaml` —
`type` picks the widget, `position` + `size` lay it out on the grid,
`data_source` wires it to one of your `/actions/{name}` endpoints. No React,
no CSS.

<table>
<tr>
<td width="50%">

**`ai-response`** — streaming chat surface

The flagship widget. Renders the assistant's turn as it streams; embeds tool calls, markdown, code blocks, files inline.

```yaml
- name: transcript
  type: ai-response
  position: { horizontal: left, vertical: high }
  size: { width: 8, height: 520 }
  empty_text: "Ask something…"
  thinking_indicator: dots
```

</td>
<td width="50%">

**`ai-chat-input`** — composer with attachments

Text input + file attach + keyboard send. Forwards the composed turn through `POST /conversations/{id}/messages`.

```yaml
- name: chat-input
  type: ai-chat-input
  position: { horizontal: left, vertical: low }
  size: { width: 12, height: auto }
  placeholder: "Message Hexgate Guard…"
  rows: 2
```

</td>
</tr>
<tr>
<td>

**`metrics`** — KPI strip

A row of labeled stat tiles. Pulls its values from a `data_source` action; auto-refreshes when a button-group action lists it in `refresh:`.

```yaml
- name: kpis
  type: metrics
  size: { width: 12, height: auto }
  columns: 4
  data_source: { action: change_summary }
  metrics:
    - { id: new, label: "New", format: number }
```

</td>
<td>

**`table`** — scrollable data grid

Header row + virtualized rows. Sourced from an action that returns rows; can be refreshed by a button.

```yaml
- name: changes
  type: table
  size: { width: 12, height: auto }
  data_source: { action: change_table }
  has_header: true
  empty_text: "No changes yet."
```

</td>
</tr>
<tr>
<td>

**`tool-calls`** — live tool log

Shows each tool the agent calls in real time, with arguments, status, and result. Default landing surface for any unaddressed tool call.

```yaml
- name: tools
  type: tool-calls
  position: { horizontal: right, vertical: high }
  size: { width: 4, height: 520 }
  empty_text: "Tool calls will appear here."
```

</td>
<td>

**`markdown`** — rich text + code

Static markdown sourced from a string, or live markdown that the agent updates via a data source (e.g. a runbook the agent edits).

```yaml
- name: runbook
  type: markdown
  size: { width: 8, height: auto }
  data_source: { action: get_runbook }
```

</td>
</tr>
<tr>
<td>

**`form`** — structured input

Labeled fields the user submits as one payload to an action. Each field declares its type; submit fires `POST /actions/{name}`.

```yaml
- name: deploy
  type: form
  size: { width: 6, height: auto }
  action: deploy_service
  fields:
    - { name: env, label: Environment, type: text }
    - { name: replicas, label: Replicas, type: number }
```

</td>
<td>

**`button-group`** — actions row

A row of buttons, each tied to an action. Optional `refresh:` list re-pulls the named widgets after the action completes — the basis for the lifecycle dashboards in ITSM / DevOps.

```yaml
- name: ops
  type: button-group
  size: { width: 12, height: auto }
  buttons:
    - { label: "Refresh", action: refresh_changes,
        refresh: [change-metrics, change-table] }
```

</td>
</tr>
</table>

Four more widgets ship for layout and inputs: `dropdown`, `page-header`, `page-footer`, `spacer`. See [`custom-UI/src/registry/builtin.ts`](custom-UI/src/registry/builtin.ts) for the canonical registry and [demo/agent-server/src/agent_server/ui/](demo/agent-server/src/agent_server/ui/) for complete `ui.yaml` examples (the ITSM and DevOps agents stitch most of the widgets together into a live ops dashboard).

---

## The two things a developer configures

1. **`ui.yaml`** — which widgets, where, and the accent color. Placed/served by
   the developer backend (`GET /agents/{id}/ui`).
2. **A backend** conforming to [CONTRACT.md](CONTRACT.md): five
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
PYTHONPATH=proxy-server/src:demo/agent-server/src:packages/hexa-events/src \
  proxy-server/.venv/bin/python demo/scripts/e2e_check.py
```

See [demo/scripts/README.md](demo/scripts/README.md) for all smoke checks and
[custom-UI/docs/](custom-UI/docs/) for the widget catalog and YAML reference.

---

## License

[MIT](LICENSE) © Hexamind.
