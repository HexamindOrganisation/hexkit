# Roadmap to v1

Full punch list to reach v1 of the unified AI agent platform described in
[specs.md](specs.md). Grouped by domain, ordered roughly by dependency.

Items marked **[x]** are done.

---

## Runtime backend (execution plane)

### Core

- [x] Normalized event schema
- [x] `UnifiedAgentRuntime` ABC
- [x] Manifest model + loader
- [x] Agent registry / discovery
- [x] FastAPI + SSE server
- [x] LangChain adapter (basic)
- [x] Verify LangChain adapter end-to-end with real key (deltas, tool events, completed output)
- [x] Emit `trace.span` events (LangGraph node entry/exit) — needed before observability UI
- [x] Emit `state.update` events (LangGraph state diffs after each node) — needed for "agent state" UI panels
- [x] Unit tests with a fake adapter (proves protocol/registry/server without LC)

### Runtime isolation

Spec calls this out as important; we're in-process today.

- [x] Subprocess worker protocol: same `UnifiedAgentRuntime` shape, transport = JSON-lines over stdio
- [x] Worker process supervisor (spawn, healthcheck via `health` RPC, EOF crash detection — explicit restart)
- [x] `RemoteAdapter` in the registry that proxies the local protocol to the worker
- [x] Per-agent venv via `uv` (fallback `python -m venv` + pip); cached by `requirements` hash
- [ ] Container runner (Docker) — optional second isolation transport

### Additional frameworks

Each one exercises the abstraction; expect event-schema tweaks.

- [x] OpenAI Agents SDK adapter
- [x] Google ADK adapter
- [x] LangGraph / DeepAgents (aliases to the LangChain adapter; both produce `CompiledStateGraph`)
- [ ] Pydantic AI

### Control / HITL

- [x] `cancel(run_id)` on the protocol + `POST /agents/{id}/runs/{run_id}/cancel` route (event-boundary cancellation; in-memory state, see README limitations)
- [ ] `approval.requested` flow: pause, surface to UI, resume endpoint
- [ ] Tool execution gating ("require approval before tool X")

---

## Platform backend (control plane)

Entire new service. Stateful, security-sensitive. Per spec, separate from runtime.

- [ ] Service scaffold (FastAPI + Postgres + Alembic, or chosen stack)
- [ ] Auth (OIDC / JWT) + user model
- [ ] RBAC (roles, permissions, policy enforcement points)
- [ ] Tenant model + tenant-scoped resources
- [ ] Conversation persistence (threads, messages, runs, events)
  - Sink that consumes the runtime's SSE stream and writes events durably
- [ ] Secret vaulting (env-var values referenced by `manifest.env`)
- [ ] App registry (which agents are deployed to which tenant, by version)
- [ ] YAML app config storage (the UI's widget layout per app/tenant)
- [ ] Observability storage: traces, runs, token counts, latencies
- [ ] Quotas & rate limiting (per tenant, per agent, per model)
- [ ] Billing meters
- [ ] Audit log
- [ ] Admin API to register/update/decommission agents
- [ ] Routing layer: `platform.example.com/app/{tenant}/{agent}` → resolves to a runtime instance

---

## UI system

### `custom-UI` library

- [x] React YAML-driven widget library
- [x] Standard widget: chat view (`ai-response` + `ai-chat-input`, message-stream-aware)
- [x] Standard widget: `tool-calls` panel consuming routed `tool-call` events
- [ ] Standard widget: tool catalog (from `/tools`)
- [ ] Standard widget: trace timeline (from `trace.span` events)
- [ ] Standard widget: state inspector (from `state.update` events)
- [ ] Standard widget: approval prompt (`approval.requested`)

### `front-app` shell

- [x] Slice 1 — foundation: React Router + AppShell + Nav, placeholder routes
- [x] Slice 2 — chat E2E: AgentsHome, AgentChat, RuntimeBridge wired to SSE + cancel
- [x] Slice 3 — per-agent `ui.yaml` served by runtime; default chat as fallback
- [ ] Slice 4 — secrets CRUD UI + runtime secret store + worker env injection
- [ ] Slice 5 — settings page (theme, runtime URL, log verbosity); `GET /config` endpoint
- [ ] Auth integration with platform backend (deferred until platform backend exists)
- [ ] App config loader fetching layout from platform backend (deferred)

---

## Cross-cutting

- [ ] End-to-end deployment recipe (docker-compose: runtime + platform + postgres + UI)
- [ ] Logging / structured logs in both backends
- [ ] OpenTelemetry export (traces → Jaeger/Tempo, metrics → Prometheus)
- [ ] CI: lint, type-check (mypy/pyright), tests, build
- [ ] Versioning policy: `RuntimeEvent` schema version, manifest schema version

---

## Suggested milestones

### M1 — "Runtime v0" — **shipped**

- LangChain / LangGraph / DeepAgents adapter (`astream_events`-based; `trace.span`, `state.update`, tool events)
- OpenAI Agents SDK adapter
- Google ADK adapter
- Subprocess isolation + per-agent venvs via `uv`
- `cancel(run_id)` end-to-end
- 42-test suite (in-process + subprocess + multi-file + venv)

### M2 — "Front-app v0" — **in progress (Slices 1–3 shipped)**

- AgentsHome + AgentChat + cancel in the browser
- Per-agent `ui.yaml` (Slice 3, shipped)
- `tool-calls` widget in `agent-ui` lib (shipped)
- Secrets page + runtime secret store (Slice 4, next)
- Settings page + `GET /config` (Slice 5)

### M3 — "Control plane skeleton"

- Platform backend service scaffold: auth, tenants, conversation persistence
- App registry (which agent runs where)
- Replace in-memory secret store with vaulted secrets

### M4 — "Observability + HITL"

- Trace timeline widget consuming `trace.span` events
- State inspector widget consuming `state.update` events
- `approval.requested` flow + tool-execution gating
- OpenTelemetry export from the runtime

### M5 — "Polish"

- Pydantic AI adapter
- Container isolation runner (Docker)
- `platform wrap` CLI
- Quotas, audit log, billing meters
