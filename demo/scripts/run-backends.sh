#!/usr/bin/env bash
# Launch the HexaUI backends for local dev — agent-server (:8080) + proxy (:8000)
# on a throwaway SQLite DB (no Postgres needed). Run from the repo root under WSL:
#
#     bash demo/scripts/run-backends.sh
#
# Then in a Windows terminal:  cd front-app && npm run dev   (→ http://localhost:5173)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

export PLATFORM_FERNET_KEY="${PLATFORM_FERNET_KEY:-$(platform-backend/.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')}"
export PLATFORM_DATABASE_URL="${PLATFORM_DATABASE_URL:-sqlite+aiosqlite:////tmp/hexa_dev.sqlite}"
export PLATFORM_AGENT_BACKEND_URL="http://127.0.0.1:8080"

# Stop by PORT, never `pkill -f agent_server` — that pattern matches this very
# script's command line and would SIGTERM the launcher itself.
cleanup() { fuser -k 8080/tcp 8000/tcp 2>/dev/null || true; }
trap cleanup EXIT INT TERM

# Set AGENT_ENABLE_LLM=1 to route the `probe` agent to the real OpenAI-backed
# LLMAgent when an openai_api_key is forwarded (else it falls back to echo).
export AGENT_ENABLE_LLM="${AGENT_ENABLE_LLM:-0}"

echo "starting agent-server :8080 (AGENT_ENABLE_LLM=$AGENT_ENABLE_LLM) …"
PYTHONPATH=demo/agent-server/src \
  backend-runtime/.venv/bin/python -m agent_server &

echo "starting proxy :8000 (sqlite: $PLATFORM_DATABASE_URL) …"
PYTHONPATH=demo/proxy/src:demo/packages/hexa-events/src \
  platform-backend/.venv/bin/python -m platform_backend &

echo "both up. open the web app with: (in front-app)  npm run dev  →  http://localhost:5173"
echo "Ctrl-C to stop both."
wait
