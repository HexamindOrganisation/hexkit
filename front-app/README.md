# front-app

The **HexaUI shell** — the user-facing web app. It wraps the
[`agent-ui`](../custom-UI/) library (`<AgentUI>`, rendered from each agent's
`ui.yaml`) in constant chrome and talks to the [proxy](../demo/proxy/) over
HTTP + SSE through a single origin (`/api/*`).

```
┌──────────────────────────────────────────────────────────────┐
│  Sidebar (folding)              Header (agent picker)         │
│   New session · Files · Settings                              │
│   cross-agent history grouped by folders                      │
├──────────────────────────────────────────────────────────────┤
│  MAIN — <AgentUI> from the agent's ui.yaml                    │
│   greeting (empty state) → chat: transcript + composer        │
└──────────────────────────────────────────────────────────────┘
                              │  Vite proxy /api/* → http://127.0.0.1:9000
                              ▼                         (demo/proxy)
```

Single-user: no login. The active agent's `main_color` is the only accent in
the product.

## Run it

```bash
# backends (from repo root, WSL) — see demo/scripts
AGENT_ENABLE_LLM=1 bash ../demo/scripts/run-backends.sh   # proxy :9000, agent-server :9080

# this app
npm install
npm run dev                                               # http://localhost:9173
```

Open <http://localhost:9173>, pick an agent from the top bar, and send a
message. Add a provider key in **Settings** for real model replies (otherwise
agents fall back to a deterministic echo). The Vite dev server proxies `/api/*`
to the platform backend; override with `PLATFORM_BACKEND_URL` if it's elsewhere.

## Routes

| Path | Page |
|---|---|
| `/` | Greeting (empty state) → chat once a message is sent (lazy conversation create) |
| `/c/:id` | An existing conversation |
| `/files` | The file library (upload / rename / delete; attach from the composer) |
| `/settings` | Per-user API keys (Fernet-encrypted server-side) |

## Layout

```
src/
  router.tsx              routes inside the AppShell
  layout/                 AppShell, Header, Sidebar (chrome)
  pages/                  ChatPage (mounts <AgentUI>), FilesPage, SettingsPage
  components/             Greeting, conversation/folder rows, key rows, dialogs
  hooks/                  useActiveAgent (derives agent/conversation from URL)
  api/                    typed REST client (agents, conversations, files, keys)
  runtime/
    sseStream.ts          fetch + SSE → AsyncGenerator
    runtimeBridge.ts      AgentBridge over the proxy (the translation seam)
    types.ts              mirrors the proxy's hexa event schema
  lib/                    color/theme helpers, file-format helpers
```

The key seam is [runtimeBridge.ts](src/runtime/runtimeBridge.ts): it adapts the
proxy's rich SSE event schema to `agent-ui`'s `AgentBridge` (token / message /
status / tool-call / error), and exposes the file capability + lazy
conversation creation. The proxy contract it speaks is
[demo/CONTRACT.md](../demo/CONTRACT.md).
