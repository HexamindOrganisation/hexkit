# front-app

User-facing app for the Unified AI Agent Platform. Talks to
[platform-runtime](../backend-runtime/) via HTTP+SSE and renders each
agent's UI with [agent-ui](../custom-UI/).

Current state: **Slice 3 of 5** — chat E2E plus per-agent `ui.yaml`
served by the runtime, with the bundled default chat as the fallback.
Foundation routes (`/secrets`, `/settings`) render placeholders awaiting
Slices 4 and 5. See [specs.md](specs.md) for the full plan.

```
┌─────────────────────────────────────────────────────────────────┐
│  Brand    Agents · Secrets · Settings        (persistent shell) │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Routes (React Router v6):                                     │
│     /                  AgentsHome   grid of agent cards         │
│     /agents/:id        AgentChat    agent-ui rendered chat      │
│     /secrets           SecretsPage  placeholder (Slice 4)       │
│     /settings          SettingsPage placeholder (Slice 5)       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                       Vite proxy /api/* → http://127.0.0.1:8080
                              │
                              ▼
                       platform-runtime
```

## Run it

In one terminal, the runtime (with at least one agent loaded):

```bash
cd ../backend-runtime
export OPENAI_API_KEY=...
export PLATFORM_AGENTS_DIR=examples
.venv/bin/python -m platform_runtime
```

In another:

```bash
cd front-app
npm install
npm run dev
```

Open <http://localhost:5173>. Pick an agent → send a message → watch
tokens stream into the transcript and tool invocations into the
right-side `Tool calls` panel. The **Cancel run** button proves the
runtime's cancel API end to end — clicking it mid-stream produces a
`Run cancelled.` system message.

The `langgraph-hello` example ships a custom [`ui.yaml`](../backend-runtime/examples/langgraph_hello/ui.yaml)
with a three-column layout (help · transcript · tool calls), an indigo
header, and a markdown help card on the left — visible proof that
per-agent UIs work without front-app changes. Other agents render the
bundled default chat layout with a small banner noting the fallback.

### Different runtime host

```bash
PLATFORM_RUNTIME_URL=http://127.0.0.1:9090 npm run dev
```

The Vite proxy uses this for `/api/*` rewrites.

## File layout

```
src/
  main.tsx                          React entry
  App.tsx                           Router root
  styles.css                        Tailwind + agent-ui CSS imports

  layout/
    AppShell.tsx                    persistent nav + <Outlet/>
    Nav.tsx                         top-bar tab navigation

  pages/
    AgentsHome.tsx                  cards grid + states
    AgentChat.tsx                   agent-ui rendered with RuntimeBridge
    SecretsPage.tsx                 placeholder (Slice 4)
    SettingsPage.tsx                placeholder (Slice 5)

  components/
    AgentCard.tsx                   one card on the home page
    HealthPill.tsx                  per-card health badge
    CapabilityBadges.tsx            streaming / tools / state / approvals

  config/
    defaultChatPage.ts              agent-ui page config (JS object)

  runtime/
    types.ts                        mirrored RuntimeEvent / AgentMetadata
    api.ts                          REST helpers (typed)
    sseStream.ts                    fetch + SSE → AsyncGenerator
    runtimeBridge.ts                AgentBridge over the runtime
```

> **Pending migration.** The runtime's event schema has moved to the
> Fortify-shared shape (`event_type` discriminator, block model, `RunNode`
> hierarchy — see
> [backend-runtime/README.md](../backend-runtime/README.md#event-schema)).
> This front-app still consumes the previous `RuntimeEvent` shape
> (`message.delta` / `tool.start` / `seq` / …); `types.ts` and
> `runtimeBridge.translate` have not yet been updated. Until they are, the
> references below describe the old vocabulary.

The interesting file is [runtimeBridge.ts](src/runtime/runtimeBridge.ts) —
the translation seam between the runtime's normalized event schema and
`agent-ui`'s smaller event vocabulary. Future event types (trace timeline,
state inspector, approval prompts) plug in here.

## What's shipped (Slices 1-3) — and what's next

**Shipped:**

- React Router v6, persistent `AppShell` with top nav.
- `/` AgentsHome: cards grid, health pills, capability badges, loading
  skeleton, empty state, error banner.
- `/agents/:id` AgentChat: metadata + `ui.yaml` fetched in parallel,
  `RuntimeBridge` wired to SSE, working **Cancel run** button.
- Per-agent YAML: `GET /agents/:id/ui` consumed; default chat used as
  fallback with a small "rendering the default" hint banner.
- Tool calls routed into the `tool-calls` widget (added to `agent-ui`)
  instead of polluting the chat transcript as system messages.
- Typed runtime client (`api.ts`, `sseStream.ts`, `types.ts`,
  `runtimeBridge.ts`) — same boundary every later slice extends.

**Coming next:**

- Slice 4 — `/secrets` page + runtime secret store + worker env
  injection at spawn time. (Spec: [specs.md](specs.md))
- Slice 5 — `/settings` page + `GET /config` endpoint (theme, runtime
  URL, log verbosity, version info).

**Deferred (per spec):**

- Multi-turn conversation persistence — needs platform backend.
- Agent registration via the UI — drop folders into `PLATFORM_AGENTS_DIR`.
- Markdown / code-block rendering of message bodies (`agent-ui`'s
  `markdown` widget can be wired into per-agent YAMLs today).
- Auth.

See [specs.md](specs.md) for the full slice plan and rationale.
