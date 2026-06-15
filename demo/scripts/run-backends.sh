#!/usr/bin/env bash
# Launch the HexaUI backends for local dev — agent-server (:8880) + proxy (:8800)
# on a throwaway SQLite DB (no Postgres needed). Run from the repo root under WSL:
#
#     bash demo/scripts/run-backends.sh
#
# Then in a Windows terminal:  cd front-app && npm run dev   (→ http://localhost:8873)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

export PLATFORM_FERNET_KEY="${PLATFORM_FERNET_KEY:-$(proxy-server/.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')}"
export PLATFORM_DATABASE_URL="${PLATFORM_DATABASE_URL:-sqlite+aiosqlite:////tmp/hexa_dev.sqlite}"
# Pre-create the demo users (alice@example.com, bob@example.com, …) on
# first boot so the demo has populated accounts to log into. Idempotent —
# rerunning never overwrites existing rows.
export PLATFORM_DEMO_USERS_FILE="${PLATFORM_DEMO_USERS_FILE:-demo-users.yaml}"
export PLATFORM_AGENT_BACKEND_URL="http://127.0.0.1:8880"

# Stop by PORT, never `pkill -f agent_server` — that pattern matches this very
# script's command line and would SIGTERM the launcher itself.
cleanup() { fuser -k 8880/tcp 8800/tcp 2>/dev/null || true; }
trap cleanup EXIT INT TERM

# Set AGENT_ENABLE_LLM=1 to route the `probe` agent to the real OpenAI-backed
# LLMAgent when an openai_api_key is forwarded (else it falls back to echo).
export AGENT_ENABLE_LLM="${AGENT_ENABLE_LLM:-0}"

# Source the agent-server secrets (OPENAI_API_KEY, HEXGATE_KEY) into the
# environment so they reach the agent-server process. The agents read
# OPENAI_API_KEY from the env first and only fall back to a per-user key from
# the Settings UI, so a key here is the reliable default — no frontend key
# needed. Values in .env take effect (same as the `register` make target); the
# agent-server also self-loads this file via python-dotenv, so sourcing here is
# belt-and-suspenders that also works if dotenv isn't installed.
if [ -f demo/agent-server/.env ]; then
  set -o allexport
  . demo/agent-server/.env
  set +o allexport
fi

echo "starting agent-server :8880 (AGENT_ENABLE_LLM=$AGENT_ENABLE_LLM) …"
PYTHONPATH=demo/agent-server/src \
  demo/agent-server/.venv/bin/python -m agent_server &

echo "starting proxy :8800 (sqlite: $PLATFORM_DATABASE_URL) …"
PYTHONPATH=proxy-server/src:packages/hexa-events/src \
  proxy-server/.venv/bin/python -m platform_backend &

echo "both up. open the web app with: (in front-app)  npm run dev  →  http://localhost:8873"
echo "Ctrl-C to stop both."
wait
