# front-app — Specification

The user-facing application for the Unified AI Agent Platform: an
operator/end-user shell that talks to the
[platform-runtime](../backend-runtime/) and renders each agent's UI via
the [agent-ui](../custom-UI/) widget library.

## Vision

A multi-page React app with three concerns:

1. **Talk to agents.** Pick from the agents loaded by the runtime, send
   messages, watch streamed responses, cancel runs.
2. **Manage framework secrets.** Add/update/remove API keys (OpenAI,
   Google, Anthropic, …) used by the agents.
3. **Tweak the platform.** App-level settings: runtime URL, theme, UI
   preferences.

Each agent renders its own UI from a per-agent YAML (consumed by
`agent-ui`). When an agent has no YAML, the app falls back to a built-in
default chat layout. Multiple agents → multiple visual identities, by design.

**Future** — the foundation supports agents emitting UI updates at
runtime via `agent-ui`'s `tool-call` widget-routing event. v0 only
consumes a static per-agent YAML; dynamic UI generation comes later.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│ Browser  (Vite + React 18 + Tailwind + React Router v6)          │
│                                                                  │
│  /                       AgentsHome    list registered agents    │
│  /agents/:id             AgentChat     per-agent UI (YAML)       │
│  /secrets                SecretsPage   manage framework keys     │
│  /settings               SettingsPage  runtime URL, theme, prefs │
│                                                                  │
│  Shared:                                                         │
│    AppShell              top nav + content area                  │
│    RuntimeBridge         per-agent AgentBridge implementation    │
│    runtime/api           REST helpers (typed)                    │
│    runtime/sseStream     fetch + SSE parser → typed events       │
└──────────────────────────────────────────────────────────────────┘
                            │
                       Vite dev proxy /api/* → http://127.0.0.1:8080
                            │
                            ▼
                  platform-runtime (FastAPI + SSE)
```

The "runtime/" client layer is the **only place** in the front-app that
knows about HTTP/SSE wire details. Pages talk to it through typed
functions; nothing else mints URLs.

---

## Pages

### `/` — AgentsHome

A landing page listing every agent the runtime has loaded.

**Renders:** for each agent (`GET /agents`), a card showing
`name`, `framework`, `description`, `capabilities` (badges for streaming
/ tools / state / approvals), and a "Chat" CTA linking to
`/agents/:id`. Status pill from `GET /agents/:id/health`.

**Loading / empty states** — both styled, no spinner-of-doom:
- Loading: skeleton cards.
- Empty: "No agents loaded. Check `PLATFORM_AGENTS_DIR`."
- Runtime unreachable: error banner pointing at the runtime URL setting.

### `/agents/:id` — AgentChat

The per-agent UI. This is where the bulk of the user time is spent.

**Flow:**
1. Fetch `GET /agents/:id/metadata` for framework / capabilities.
2. Fetch `GET /agents/:id/ui` to load the agent's `ui.yaml`.
   - On `200`: parse the YAML, hand it to `agent-ui` as the page config.
   - On `404`: fall back to the bundled default chat layout (see
     `src/config/defaultChatPage.ts`).
3. Construct a `RuntimeBridge` bound to `(agent_id, framework)`.
4. Render `<AgentUI config={...} agent={bridge} dispatcher={...} />`.

**Bridge dispatcher actions:**
- `cancel-run` → calls the runtime's `POST /runs/{run_id}/cancel`.
- Future: `approve` for `approval.requested`, others as features land.

**Conversation lifetime:** in-memory, per browser session. Navigating
away from the page or switching agents drops the conversation. Refresh
also drops it. Real persistence lands with the platform backend.

**Theming:** the YAML's `page.main_color` overrides the app-shell
theme for this route only. Each agent can have its own visual identity.

### `/secrets` — SecretsPage

CRUD for framework secrets. v0 storage is a plaintext JSON file on the
runtime host (see Runtime changes below).

**Renders:**
- List of declared env-var names across all loaded agents (collected
  from each manifest's `env:` field — read-only view of what's expected).
- For each, a row showing the key name and a "Set" / "Update" / "Clear"
  button. Values are masked (`••••`) when displayed; never echoed in
  the DOM.
- "Add custom key" button for env vars not declared in any manifest.

**Security posture:** documented as v0-only on the page itself
("Plaintext on host. Not for production. Move to a real secret manager
before deploying."). Persistence is a JSON file at
`~/.platform_runtime/secrets.json` with 0600 permissions; the runtime
injects them into worker process environments at spawn time.

### `/settings` — SettingsPage

App-level configuration, persisted in `localStorage`:
- **Runtime URL** override (default `/api`, dev proxy target is set via
  `PLATFORM_RUNTIME_URL`).
- **Theme** — light / dark / system.
- **Event log verbosity** — which `RuntimeEvent` types are shown in any
  raw-event debugging panel (off / errors only / all).

Plus a read-only view of:
- Runtime version and isolation mode (`GET /config` on the runtime).
- Front-app version (from `package.json`).

---

## Components

```
src/
  main.tsx                          React entry; router + Tailwind
  App.tsx                           AppShell + <Routes>
  layout/
    AppShell.tsx                    top nav (Agents | Secrets | Settings)
    Nav.tsx                         link list
  pages/
    AgentsHome.tsx
    AgentChat.tsx                   wraps <AgentUI/> from agent-ui
    SecretsPage.tsx
    SettingsPage.tsx
  components/
    AgentCard.tsx
    HealthPill.tsx
    CapabilityBadges.tsx
    SecretRow.tsx
    PageHeader.tsx                  (the front-app's own header, NOT the
                                     agent-ui widget)
  config/
    defaultChatPage.ts              page object handed to AgentUI when
                                     /agents/:id/ui returns 404
  runtime/
    types.ts                        RuntimeEvent, AgentMetadata, Secret,
                                     RuntimeConfig
                                     (NOTE: still the pre-migration event
                                     shape; the runtime now emits the
                                     Fortify-shared schema — event_type,
                                     block model, RunNode hierarchy. types.ts
                                     + runtimeBridge.translate migration is
                                     pending. See backend-runtime README.)
    api.ts                          listAgents, getMetadata, getUiYaml,
                                     getHealth, cancelRun, getSecrets,
                                     putSecret, deleteSecret, getConfig
    sseStream.ts                    fetch + SSE → AsyncGenerator<RuntimeEvent>
    runtimeBridge.ts                AgentBridge over the SSE stream
    secrets.ts                      typed helpers for the secrets API
  state/
    settings.ts                     localStorage-backed settings store
                                     (Zustand or context — see below)
```

### State management

- **Server state** (agents, metadata, tools, health, secrets): plain
  `useEffect + fetch` per page. No data-fetching library for v0; pages
  are small enough. Swappable to React Query if pain emerges.
- **Settings** (runtime URL, theme, log verbosity): React Context backed
  by `localStorage`. ~30 lines, no dependency.
- **Conversation state inside a chat**: owned by `agent-ui` internally
  via the `AgentBridge` it's given. The front-app doesn't duplicate it.

---

## Runtime changes required for v0

The front-app needs **four new endpoints and one storage module** in
backend-runtime. These are in scope for the front-app slice — the FE
cannot ship without them.

### 1. `GET /agents/{id}/ui`

Returns the agent's `ui.yaml` file as `text/yaml` if a file named
`ui.yaml` exists in the agent's directory; otherwise `404`. No
validation server-side — `agent-ui` validates on the client. Read-only
in v0.

### 2. `GET /secrets`

Returns `[{ "name": "OPENAI_API_KEY", "present": true }, …]`. Lists
keys only — values are **never** returned over the wire. Aggregates the
union of (a) keys declared in any manifest's `env:` field and (b) keys
currently stored.

### 3. `PUT /secrets/{key}`

Body: `{ "value": "..." }`. Writes to
`~/.platform_runtime/secrets.json` (mode `0600`). Idempotent.

### 4. `DELETE /secrets/{key}`

Removes the key. Returns 204.

### 5. Secret injection at worker spawn

The `WorkerSupervisor` accepts an env mapping (already does). The
registry, when constructing a supervisor in subprocess mode, augments
the env with values from the secret store for every key in
`manifest.env`. **Keys not in the store are left unset** — the agent
fails at first use with the normal "missing credential" error, no
silent fallbacks.

### 6. `GET /config`

Returns `{ "version": "0.1.0", "isolation": "subprocess", "agents_dir":
"...", "frameworks_supported": [...] }`. Powers the Settings page's
read-only section.

### Out of scope for v0 runtime work

- Hot-reload of agents (no rescan endpoint).
- Encryption-at-rest for secrets.
- Auth on any of these endpoints (the runtime trusts its caller; the
  control plane handles auth later).
- Secret store survival of runtime upgrades (we'll likely change the
  file format; document as "delete and re-enter on upgrade until v1").

---

## Stack

| Layer | Choice | Reason |
|---|---|---|
| Build | Vite | Already used by `custom-UI`; instant HMR; trivial dev proxy |
| Framework | React 18 | Required by `agent-ui` peer dep |
| Language | TypeScript (strict) | Wire types are typed end to end |
| Styling | Tailwind 3.x + `agent-ui/tailwind-preset` | Same theme tokens as the lib |
| Router | React Router v6 | Bookmarkable URLs, nested routes, well-known |
| State (server) | `useEffect + fetch` | YAGNI for v0; trivial to swap later |
| State (settings) | React Context + `localStorage` | No new dep |
| Lib integration | `agent-ui` via `file:../custom-UI` | Local dev coupling; remote install later |

No data-fetching lib, no global state lib, no UI lib beyond agent-ui.
The dependency budget is intentional: every added dep is a re-evaluation
later for the "industrial v1" cut.

---

## v0 scope — explicit list

**In:**
- `/`, `/agents/:id`, `/secrets`, `/settings` routes.
- Agent picker on home, switch by clicking.
- Per-agent YAML rendering with default-chat fallback.
- Cancel button wired to the runtime's cancel API.
- Secrets CRUD against the new runtime endpoints.
- Settings: runtime URL, theme, log verbosity.
- Read-only display of runtime version + isolation mode.
- Loading / empty / error states on every page.

**Out (deferred, designed-for):**
- Multi-turn conversation persistence (waiting on platform backend).
- Agent registration via the UI (deferred per Q&A round 1).
- Live agent editing (model, instructions, YAML) via the UI.
- Encryption-at-rest for secrets.
- Auth / RBAC / tenants.
- Markdown rendering, code blocks, file uploads in chat.
- The trace timeline, state inspector, approval prompt widgets in
  agent-ui (they need to exist first).
- Dynamic UI generation from agent events (`tool-call` routing exists
  in the lib; needs adapter mapping plumbing).

---

## Iteration paths the v0 deliberately keeps open

1. **Replace the default chat YAML with per-agent overrides.** Adding a
   `ui.yaml` to any example agent under `examples/` makes that agent
   render with its own layout. Zero front-app changes.
2. **Add new event-type handling.** Extending `runtimeBridge.translate`
   with a case for `approval.requested` (and a corresponding agent-ui
   widget) is the smallest possible HITL hook.
3. **Dynamic UI updates.** Agents can already emit `tool-call`
   payloads routed to widgets by name; the bridge just needs a mapping
   from a platform event (likely `state.update` with a structured
   payload) to `agent-ui`'s `tool-call` event.
4. **Promote `RuntimeBridge` into agent-ui itself.** Once the API is
   stable, the bridge could ship inside the library as
   `createPlatformRuntimeBridge({ agentId, framework })` so other
   front-ends don't reimplement it.
5. **Auth layer.** All API calls already go through `runtime/api.ts`;
   adding an auth header is a one-file change.

---

## Implementation order

Suggested slicing to keep each slice independently demoable:

1. **Slice 1 — Foundation.** Vite + Tailwind + React Router + AppShell.
   Empty `/`, `/secrets`, `/settings` routes that render placeholders.
   Dev proxy works. No runtime calls yet.

2. **Slice 2 — Chat E2E.** AgentsHome lists `GET /agents`. Click an
   agent → `/agents/:id`. Default chat YAML renders. Bridge wired up.
   Cancel button works. **This is the first full end-to-end run.**

3. **Slice 3 — Per-agent YAML.** Implement `GET /agents/{id}/ui` in
   the runtime. AgentChat fetches the YAML, falls back to default on
   404. Add `ui.yaml` to one example agent to demonstrate.

4. **Slice 4 — Secrets.** Implement the four secret endpoints +
   storage module in the runtime. Build SecretsPage. Wire secret
   injection at worker spawn. Verify a previously broken agent (no
   `OPENAI_API_KEY` in shell env) starts working after the user enters
   the key via the UI.

5. **Slice 5 — Settings.** `GET /config` endpoint in the runtime.
   SettingsPage with theme + runtime URL override + log verbosity.

Each slice ends with the app demonstrably useful at its current depth;
no slice depends on a later one to ship.

---

## Non-goals (worth being explicit)

- **The front-app is not the control plane.** No multi-tenant logic, no
  RBAC, no audit trail. Those belong in a future platform-backend
  service. The front-app talks to the runtime directly today; when the
  control plane lands, the front-app's `runtime/api.ts` is the single
  layer that needs to switch its base URL.
- **The front-app does not validate agent YAMLs.** That's `agent-ui`'s
  job (diagnostics surface in the browser console in v0).
- **No SSR.** Pure client-side. Vite preview / static hosting is fine.

---

## Open questions for follow-up rounds

- Should `/agents/:id/ui` accept a `ui.yaml` **and** a `ui.json`? Probably
  not — pick one (YAML, matches the rest of the spec).
- How to surface tool events visually? v0 dumps them as system messages
  in the transcript. A side panel "Tool calls" widget would be cleaner
  but lives outside the chat — addressable via the per-agent YAML once
  someone writes one.
- The "raw event log" debug panel — top-level (across pages) or per
  agent route? v0: per agent route, collapsible, off by default.

These don't block implementation start. We can revisit during Slice 3+.
