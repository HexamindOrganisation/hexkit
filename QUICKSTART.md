# Quickstart — Running a Small Agent App Locally

This guide gets you from a fresh clone to a working chat with a demo agent in your browser.

## What you're running

Three services talk to each other:

```
front-app (Vite, :5173)
   └─→ proxy (FastAPI, :8000)        platform backend: conversations, files, auth
          └─→ agent-server (FastAPI, :8080)   serves demo agents (Probe, Orbit, Atlas, Forge)
                 └─→ OpenAI / Google APIs (optional — needs keys for real LLM replies)
```

Without API keys the agents reply with an echo placeholder. That's fine for a first run.

## Prerequisites

- **Python 3.11+** with [`uv`](https://docs.astral.sh/uv/) installed
- **Node.js 18+** with `npm`

## One-time setup

From the repo root (`Agent-Package/`):

```bash
make setup
```

This creates Python venvs, builds the `custom-UI` library, and installs the front-app `node_modules`.

## Run it

Easiest path — one command, one terminal:

```bash
make dev
```

That launches the agent-server (:8080), proxy (:8000) and Vite dev server (:5173) together; `Ctrl-C` tears everything down. Run `make help` to see all available targets (lint, test, typecheck, …).

### Two-terminal alternative

If you prefer to see each service's logs separately:

#### Terminal 1 — backends (proxy + agent-server)

```bash
bash demo/scripts/run-backends.sh
```

This launches both the agent-server on `:8080` and the proxy on `:8000`, and cleans up on `Ctrl-C`.

To enable real LLM replies (instead of echo), prepend the env var:

```bash
AGENT_ENABLE_LLM=1 bash demo/scripts/run-backends.sh
```

You'll still need to add your `OPENAI_API_KEY` or `GOOGLE_API_KEY` in the app's Settings page once the UI loads — the proxy encrypts and forwards keys per turn rather than reading them from your shell.

#### Terminal 2 — frontend

```bash
cd front-app && npm run dev
```

Open <http://localhost:5173>.

## What you should see

1. Loading the app redirects you to **/login** (the route guard fires).
2. Log in as **`dev01@hexamind.ai`** / **`hexademo`** (the dev seed creates this account on first run). Or sign up a new account at **/signup**.
3. The chat shell loads with an empty greeting.
4. Click the agent picker in the top bar and choose **Probe** (or any of the four demo agents).
5. Type a message and send.
6. With `AGENT_ENABLE_LLM=1` and a key in Settings → a real LLM reply.
   Without → an echo of your message (this confirms the full pipeline works).

> **Production:** set `PLATFORM_SEED_DEV_USER=false` to skip the dev account seed.

## Smaller alternative — starter-agent only

If you want the minimum possible backend (a single "Echo" agent in ~150 lines, meant as a template for writing your own), use `demo/starter-agent` instead of `demo/agent-server`:

```bash
cd Agent-Package/demo/starter-agent
uv venv .venv
uv pip install --python .venv -e '.[dev]'

AGENT_HOST=127.0.0.1 AGENT_PORT=8080 .venv/bin/python -m starter_agent
```

Then run the proxy and front-app as usual. The proxy talks to whatever is on `:8080`, so it doesn't care which one is there.

## Configuration

Defaults work out-of-the-box. The variables you might touch:

| Variable | Default | Where |
|---|---|---|
| `AGENT_PORT` | `8080` | agent-server / starter-agent |
| `AGENT_ENABLE_LLM` | unset (echo mode) | agent-server |
| `PLATFORM_PORT` | `8000` | proxy |
| `PLATFORM_DATABASE_URL` | `sqlite+aiosqlite:////tmp/hexa_dev.sqlite` | proxy |
| `PLATFORM_AGENT_BACKEND_URL` | `http://127.0.0.1:8080` | proxy → agent-server |
| `PLATFORM_FERNET_KEY` | auto-generated | proxy (encrypts stored API keys) |

The Vite dev server proxies `/api/*` → `http://127.0.0.1:8000`, so the frontend doesn't need its own env vars in the default setup.

## Troubleshooting

**Port already in use.** Find and kill the stale process:

```bash
lsof -i :8080   # agent-server
lsof -i :8000   # proxy
lsof -i :5173   # front-app
```

**`.venv` not found.** Re-run `bash demo/scripts/setup.sh`.

**LLM replies look like echoes.** Either `AGENT_ENABLE_LLM` isn't set when starting the backends, or no API key has been added in the Settings page yet.

**Database feels stale.** The default SQLite file lives at `/tmp/hexa_dev.sqlite` — delete it to reset all conversations and users.

## Next steps

- Read [`demo/README.md`](demo/README.md) for the deeper architecture (event schema, agent contract, framework translators).
- Read [`custom-UI/README.md`](custom-UI/README.md) to understand how each agent's `ui.yaml` becomes a rendered chat surface.
- Copy `demo/starter-agent` and modify it to plug in your own agent backend.
