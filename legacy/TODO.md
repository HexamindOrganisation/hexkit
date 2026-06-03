> **⚠️ SUPERSEDED (pre-pivot).** Roadmap for the dropped *unified agent
> runtime*. Not the current plan — see the root [README](../README.md) and
> [demo/HANDOFF.md](../demo/HANDOFF.md). Kept for historical reference.

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
- [x] Emit `trace_span` events (LangGraph node entry/exit) — needed before observability UI
- [x] Emit `state_update` events (LangGraph state diffs after each node) — needed for "agent state" UI panels
- [x] Migrate event schema to the Fortify-shared shape (block model, `RunNode` hierarchy, `event_type` discriminator); keep `trace_span`/`state_update` as additive extensions
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

### Control / HITL

- [x] `cancel(run_id)` on the protocol + `POST /agents/{id}/runs/{run_id}/cancel` route (event-boundary cancellation; in-memory state, see README limitations)
- [x] `approval_requested`/`approval_resolved` events, `resume()` protocol hook, `POST .../approvals/{id}` endpoint, and a reference suspend/resume loop in `FakeRuntime`
- [ ] `approval_requested` flow: surface to UI (front-app translate + approval prompt widget)
- [ ] Tool execution gating ("require approval before tool X")

### UI-triggered actions

- [x] `actions.py` convention + manifest `actions:` field
- [x] `ActionHost` (local + remote), action loader, IPC `action` method
- [x] `POST /agents/{id}/actions/{name}` route returning `{result, events}`
- [x] Side-effect events route back to widget inboxes via the bridge
- [ ] `dispatcher.subscribe` support: `GET /agents/{id}/actions/{name}/stream` (SSE) for live `data_source` feeds

### Multi-turn & credentials — front-end v0 prerequisites

The unified input shape (`{"messages": [{role, content}]}`) and per-user
credentials both land in the adapters so the platform backend stays
framework-blind.

- [x] LangChain / LangGraph / DeepAgents input translation (`messages` → LC message classes)
- [x] OpenAI Agents SDK input translation (`messages` → input-item list)
- [x] Google ADK input translation (session replay via `append_event`; in progress)
- [x] Per-user credentials via `InvokeRequest.context.credentials`; each adapter forwards into framework client construction
- [x] Per-call runnable/agent construction when credentials differ (cache keyed on credential hash)
- [ ] Tests: one multi-message round-trip per adapter

---

## Platform backend (control plane)

Entire new service. Stateful, security-sensitive. Per spec, separate from
runtime. The front-end v0 forces a **v0 subset** of this into existence now
(auth + conversations + per-user keys + runtime proxy). The rest stays
post-v0.

### v0 subset — required by the front-end v0

Stack: FastAPI + SQLAlchemy + **PostgreSQL** + Alembic.

- [x] Service scaffold (`platform-backend/`), FastAPI app, Alembic init, Postgres connection + docker-compose for local dev
- [x] User model + `POST /auth/signup`, `POST /auth/login` (email + password, argon2id), JWT middleware, `GET /me`
- [x] Per-user API keys: encrypted at rest (Fernet, master key from env); `GET/PUT/DELETE /me/keys/:provider`
- [x] Folders (flat, one level): `GET/POST/PATCH/DELETE /folders`
- [x] Conversations (per user, one `agent_id` each): `GET/POST/PATCH/DELETE /conversations`, `GET /conversations/:id/messages`
- [x] Message persistence (user + assistant final content; `run_id` for trace correlation)
- [x] Runtime proxy: `GET /agents`, `/agents/:id/{metadata,tools,health,ui}` passthrough
- [x] Chat route `POST /conversations/:id/messages` → assemble history into `{messages:[...]}`, inject user creds, proxy runtime SSE, save assistant message as it streams
- [x] Cancel proxy `POST /conversations/:id/cancel`
- [x] Action proxy `POST /conversations/:id/actions/:name`
- [x] Conversation auto-titling (heuristic: truncate first user message)
- [x] pytest suite for auth + conversations CRUD + proxy

### Post-v0 (full control plane)

- [ ] RBAC (roles, permissions, policy enforcement points)
- [ ] Tenant model + tenant-scoped resources
- [ ] System-default API keys (admin-configured) with per-user override
- [ ] Password reset / email verification / OAuth providers
- [ ] Durable event sink (persist full `StreamEvent` stream, not just final text)
- [ ] Streaming reconnect / replay (`Last-Event-ID`)
- [ ] App registry (which agents are deployed to which tenant, by version)
- [ ] YAML app config storage (per-tenant widget layout overrides)
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
- [ ] Standard widget: trace timeline (from `trace_span` events)
- [ ] Standard widget: state inspector (from `state_update` events)
- [ ] Standard widget: approval prompt (`approval_requested`)

### `front-app` shell — v0 (OpenWebUI-ISO, end-user oriented)

The dev-tool shell (agent grid + per-agent route) was scrapped. The new
shell is end-user oriented: landing page IS a chat, agents picked via a
search dropdown, conversations + folders in a sidebar, login required.
All calls go through the platform backend (single origin, JWT).

**Kept from the old front-app:** `runtime/sseStream.ts`, `runtime/types.ts`,
and most of `runtime/runtimeBridge.ts` (repointed at the platform backend).
Everything else (pages, layout, components, config) was deleted.

- [x] Scrap old shell; preserve `runtime/` client layer; stub `main.tsx`
- [ ] Repoint runtime client at the platform backend (base URL, JWT header, cancel/action routes)
- [ ] Auth: login + signup pages, JWT storage, authed-fetch wrapper, route guard
- [ ] App shell: sidebar (new-chat, conversation search, flat folders + conversations) + header (agent dropdown with search, user menu)
- [ ] Landing page = chat with the first registered agent, blank conversation
- [ ] Default chat config (front-app ships it): `ai-response` + `ai-chat-input` (history lives in the sidebar, not the YAML)
- [ ] Per-agent `ui.yaml` still honored (fetched via the proxy; default config as fallback)
- [ ] Conversation lifecycle UI: create on first message, rename, delete, move to folder
- [ ] Folder lifecycle UI: create, rename, delete
- [ ] Settings: per-user API keys page, profile (email / password) page
- [ ] Onboarding gate: no keys → prompt to add one before the first message
- [ ] Mobile: sidebar collapses behind a toggle

### `front-app` — post-v0

- [ ] Conversation content search (Postgres FTS)
- [ ] Message edit / regenerate / branch
- [ ] Multimodal input (attachments, paste)
- [ ] Trace / state / approval widgets (need the lib widgets first)
- [ ] App config loader fetching per-tenant layout from the platform backend

---

## Cross-cutting

- [ ] End-to-end deployment recipe (docker-compose: runtime + platform + postgres + UI)
- [ ] Logging / structured logs in both backends
- [ ] OpenTelemetry export (traces → Jaeger/Tempo, metrics → Prometheus)
- [ ] CI: lint, type-check (mypy/pyright), tests, build
- [ ] Versioning policy: `StreamEvent` schema version, manifest schema version

---

## Suggested milestones

### M1 — "Runtime v0" — **shipped**

- LangChain / LangGraph / DeepAgents adapter (`astream_events`-based; `trace_span`, `state_update`, tool events)
- OpenAI Agents SDK adapter
- Google ADK adapter
- Subprocess isolation + per-agent venvs via `uv`
- `cancel(run_id)` end-to-end
- 42-test suite (in-process + subprocess + multi-file + venv)

### M2 — "Dev-tool front-app v0" — **superseded**

The earlier dev-tool shell (agent grid, per-agent route, secrets/settings
slices) was built (Slices 1–3) then **scrapped** in favor of the
OpenWebUI-ISO end-user shell. The `tool-calls` widget and the per-agent
`ui.yaml` mechanism survive; the shell does not.

### M2′ — "End-user front-app v0" (current focus)

Reach an OpenWebUI-comparable end-user app. Spans three layers:

1. **Runtime** — input normalization (LangChain ✅, OpenAI ✅, ADK 🚧) +
   per-user credentials via `context.credentials`.
2. **Platform backend (new)** — auth, per-user keys, folders, conversations,
   message persistence, runtime SSE proxy. Postgres.
3. **Front-app (rewrite)** — login, sidebar with folders + conversations,
   agent dropdown w/ search, chat landing, settings.

Sub-slices, each independently demoable:

- **M2′.1** — Platform backend skeleton: auth + JWT + `/me` (curl-testable)
- **M2′.2** — Folders + conversations + messages CRUD (curl-testable)
- **M2′.3** — Per-user keys + runtime proxy + credential pass-through → chat works end-to-end via curl
- **M2′.4** — Front-app shell rewrite (the big UX slice)
- **M2′.5** — Onboarding, auto-titling, conversation/folder management UI, mobile

### M3 — "Multi-tenant control plane"

- RBAC, tenants, tenant-scoped resources
- System-default keys + per-user override
- App registry; per-tenant YAML config storage
- Durable event sink; streaming reconnect

### M4 — "Observability + HITL"

- Trace timeline widget consuming `trace_span` events
- State inspector widget consuming `state_update` events
- `approval_requested` flow + tool-execution gating
- `dispatcher.subscribe` live data feeds (`/actions/:name/stream`)
- OpenTelemetry export from the runtime

### M5 — "Polish"

- Pydantic AI adapter
- Container isolation runner (Docker)
- `platform wrap` CLI
- Quotas, audit log, billing meters
