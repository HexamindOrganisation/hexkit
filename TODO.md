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
- [ ] Google ADK adapter
- [ ] LangGraph / Deepagents
- [ ] Pydantic AI

### Control / HITL

- [ ] `cancel(run_id)` on the protocol + `DELETE /runs/{run_id}` route
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

- [x] React YAML-driven widget library (`custom-UI/`)
- [ ] Standard widget: chat view that consumes the SSE event stream (renders `message.delta` / `tool.start` / `tool.end`)
- [ ] Standard widget: tool catalog (from `/tools`)
- [ ] Standard widget: trace timeline (from `trace.span` events)
- [ ] Standard widget: state inspector (from `state.update` events)
- [ ] Standard widget: approval prompt (`approval.requested`)
- [ ] Auth integration with platform backend
- [ ] App config loader: fetches YAML from platform backend, renders
- [ ] `front-app/` shell wiring it all together (login → tenant select → agent select → render)

---

## Cross-cutting

- [ ] End-to-end deployment recipe (docker-compose: runtime + platform + postgres + UI)
- [ ] Logging / structured logs in both backends
- [ ] OpenTelemetry export (traces → Jaeger/Tempo, metrics → Prometheus)
- [ ] CI: lint, type-check (mypy/pyright), tests, build
- [ ] Versioning policy: `RuntimeEvent` schema version, manifest schema version

---

## Suggested milestones

### M1 — "It runs LangChain agents in prod-ish shape"

Target: 1–2 weeks of focused work.

- Verify LC adapter E2E
- Subprocess isolation transport
- `cancel(run_id)` + reconnect/resume on SSE
- Unit tests
- Chat widget in `custom-UI/` consuming the SSE stream

### M2 — "Second framework + control plane skeleton"

- OpenAI Agents SDK adapter (forces schema discipline)
- Platform backend skeleton: auth, tenant, conversation persistence, app registry
- Front-app shell login → agent picker → chat

### M3 — "Observable & multi-tenant"

- `trace.span` + `state.update` emission in LC adapter
- Trace + state widgets
- Quotas, audit log, secret vault
- `platform wrap` CLI
