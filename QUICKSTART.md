# Quickstart — Running a Small Agent App Locally

This guide gets you from a fresh clone to a working chat with a demo agent in your browser.

## What you're running

Three services talk to each other:

```
front-app (Vite, :8873)
   └─→ proxy (FastAPI, :8800)        platform backend: conversations, files, auth
          └─→ agent-server (FastAPI, :8880)   serves demo agents (Probe, Orbit, Atlas, Forge, Healthcare, DevOps)
                 └─→ OpenAI / Google APIs (optional — needs keys for real LLM replies)
```

Without API keys the agents reply with an echo placeholder. That's fine for a first run.

## Prerequisites

- **Python 3.11+** with [`uv`](https://docs.astral.sh/uv/) installed
- **Node.js 18+** with `npm`

## One-time setup

From the repo root (`HexUI/`):

```bash
make setup
```

This creates Python venvs, builds the `custom-UI` library, and installs the front-app `node_modules`.

## Run it

Easiest path — one command, one terminal:

```bash
make dev
```

That launches the agent-server (:8880), proxy (:8800) and Vite dev server (:8873) together; `Ctrl-C` tears everything down. Run `make help` to see all available targets (lint, test, typecheck, …).

### Two-terminal alternative

If you prefer to see each service's logs separately:

#### Terminal 1 — backends (proxy + agent-server)

```bash
bash demo/scripts/run-backends.sh
```

This launches both the agent-server on `:8880` and the proxy on `:8800`, and cleans up on `Ctrl-C`.

To enable real LLM replies (instead of echo), prepend the env var:

```bash
AGENT_ENABLE_LLM=1 bash demo/scripts/run-backends.sh
```

You'll still need to add your `OPENAI_API_KEY` or `GOOGLE_API_KEY` in the app's Settings page once the UI loads — the proxy encrypts and forwards keys per turn rather than reading them from your shell.

#### Terminal 2 — frontend

```bash
cd front-app && npm run dev
```

Open <http://localhost:8873>.

## What you should see

1. Loading the app redirects you to **/login** (the route guard fires).
2. Log in as one of the demo accounts (all share the same password, `hexademo`):
   - `dev01@hexamind.ai` (admin), `alice@example.com` (billing),
     `bob@example.com` (support), `carol@example.com` (no role)
   - `dana@example.com` (nurse) and `erin@example.com` (doctor) — healthcare roles
   - `frank@example.com` (viewer) and `grace@example.com` (operator) — devops roles

   The `role` only matters for HexGate-gated agents (healthcare / devops with
   `HEXGATE_KEY` set), where it scopes the per-tool policy. The accounts come
   from [`demo-users.yaml`](demo-users.yaml), upserted on
   startup when `PLATFORM_DEMO_USERS_FILE` is set (the `make dev` launcher sets
   it for you). Or sign up a fresh account at **/signup**.
3. The chat shell loads with an empty greeting.
4. Click the agent picker in the top bar and choose **Probe** (or any of the six demo agents — Probe, Orbit, Atlas, Forge, Healthcare, DevOps).
5. Type a message and send.
6. With `AGENT_ENABLE_LLM=1` and a key in Settings → a real LLM reply.
   Without → an echo of your message (this confirms the full pipeline works).

> **Production:** set `PLATFORM_SEED_DEV_USER=false` to skip the dev account seed.

## Smaller alternative — starter-agent only

If you want the minimum possible backend (a single "Echo" agent in ~150 lines, meant as a template for writing your own), use `demo/starter-agent` instead of `demo/agent-server`:

```bash
cd demo/starter-agent
uv venv .venv
uv pip install --python .venv -e '.[dev]'

# starter-agent exposes create_app(); run it with uvicorn's factory flag.
.venv/bin/uvicorn starter_agent.app:create_app --factory --host 127.0.0.1 --port 8880
```

Then run the proxy and front-app as usual. The proxy talks to whatever is on `:8880`
(its default `PLATFORM_AGENT_BACKEND_URL`), so it doesn't care which backend is there.

## Configuration

Defaults work out-of-the-box. The variables you might touch:

| Variable | Default | Where |
|---|---|---|
| `AGENT_PORT` | `8880` | agent-server / starter-agent |
| `AGENT_ENABLE_LLM` | unset (echo mode) | agent-server |
| `PLATFORM_PORT` | `8800` | proxy |
| `PLATFORM_DATABASE_URL` | `sqlite+aiosqlite:////tmp/hexa_dev.sqlite` | proxy |
| `PLATFORM_AGENT_BACKEND_URL` | `http://127.0.0.1:8880` | proxy → agent-server |
| `PLATFORM_FERNET_KEY` | auto-generated | proxy (encrypts stored API keys) |

The Vite dev server proxies `/api/*` → `http://127.0.0.1:8800`, so the frontend doesn't need its own env vars in the default setup.

## Troubleshooting

**Port already in use.** Find and kill the stale process:

```bash
lsof -i :8880   # agent-server
lsof -i :8800   # proxy
lsof -i :8873   # front-app
```

**`.venv` not found.** Re-run `bash demo/scripts/setup.sh`.

**LLM replies look like echoes.** Either `AGENT_ENABLE_LLM` isn't set when starting the backends, or no API key has been added in the Settings page yet.

**Database feels stale.** The default SQLite file lives at `/tmp/hexa_dev.sqlite` — delete it to reset all conversations and users.

**`no such column` / schema errors after a pull.** The proxy brings the SQLite schema to head via Alembic migrations on startup, so a pull that changes the schema is normally picked up on restart. The exception is a SQLite file created before this behavior existed (tables present, no `alembic_version` table): the first migration fails with "table already exists". Fix it once with `rm /tmp/hexa_dev.sqlite` and restart. (Postgres is migrated out-of-band — run `cd demo/proxy && alembic upgrade head` after a schema-changing pull.)

## Next steps

- Read [`demo/CONTRACT.md`](demo/CONTRACT.md) for the deeper architecture (event schema, agent contract, framework translators).
- Read [`custom-UI/README.md`](custom-UI/README.md) to understand how each agent's `ui.yaml` becomes a rendered chat surface.
- Copy `demo/starter-agent` and modify it to plug in your own agent backend.
