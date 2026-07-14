# gdocs-agent — a policy-gated Google-Docs agent on the HexKit contract

The "gates" demo backend. It serves **one** hexgate agent (`docs`) over the five
[CONTRACT.md](../../CONTRACT.md) endpoints. The agent:

- connects to a **fake Google Docs MCP server** (spawned over stdio by the app
  lifespan) and inherits its six tools under the `mcp-gdocs-*` namespace;
- is created with `bind_policy=True` + `name="docs_agent"`, so its policy is
  **fetched from the hexgate platform** and hot-reloaded every run — edit it in
  the dashboard's **Policies** tab and the next message reflects it;
- runs under the caller's HexKit **role** (`analyst` / `editor` / `admin`) via
  `async with hexgate.User(role=...)`, so the same call is allowed for one role
  and denied for another. A denied tool call streams as a hexgate `error` event
  and shows up as a failed call in the tool-calls widget.

This is the *runtime* side of the demo. The *definition* side — the agent code,
a diagram, and the policy — lives in the hexgate repo at
`asianf/deploy/gates-demo/notebook.py`.

## Prerequisites

- **Python ≥ 3.13** (hexgate requires it; `hexgate.mcp` spawns the MCP server).
- **A hexgate platform to bind to.** Set `HEXGATE_API_URL` + `HEXGATE_API_KEY`
  for a project whose `docs_agent` policy is seeded (the one-box demo does this
  automatically — see `asianf/deploy/`). Without a reachable platform the first
  run errors (fail-loud), by design.
- **`OPENAI_API_KEY`** — read from this process's env, or handed in-memory via
  `POST /byok {"openai_key": "sk-..."}` (the demo notebook posts it). Kept in
  process memory only — never persisted. HexKit never sends provider keys.

## Run it

```bash
uv venv --python 3.13 demo/gdocs-agent/.venv
uv pip install --python demo/gdocs-agent/.venv -e 'demo/gdocs-agent[dev]'

export HEXGATE_API_URL=http://127.0.0.1:8000   # your platform
export HEXGATE_API_KEY=fty_live_...             # or drop /tmp/hexgate_serve_key
export OPENAI_API_KEY=sk-...

demo/gdocs-agent/.venv/bin/python -m gdocs_agent    # serves on :8880
```

`:8880` is the port the HexKit proxy proxies by default
(`PLATFORM_AGENT_BACKEND_URL`), so this backend stands in as the demo's only
agent server with no proxy config. Point HexKit's front-app + proxy at it and
the picker shows one agent, **Docs Assistant**.

## Verify the contract

```bash
demo/gdocs-agent/.venv/bin/python demo/scripts/verify_backend.py http://127.0.0.1:8880
```

## Environment

| var | purpose |
|---|---|
| `HEXGATE_API_URL` / `HEXGATE_API_KEY` | platform to bind `docs_agent`'s policy from |
| `HEXGATE_SERVE_KEY_FILE` | file the demo boot writes the minted key to (default `/tmp/hexgate_serve_key`); adopted into `HEXGATE_API_KEY` if unset |
| `OPENAI_API_KEY` | BYOK — the chat model's key (env, or posted in-memory to `/byok`) |
| `HEXGATE_MODEL` | chat model (default `gpt-4o-mini`) |
| `AGENT_HOST` / `AGENT_PORT` | bind address (default `127.0.0.1:8880`) |
