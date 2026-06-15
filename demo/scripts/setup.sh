#!/usr/bin/env bash
# Bootstrap a fresh clone: Python venvs for the backends, plus the custom-UI
# library build (consumed by front-app as a file:../ link) and front-app
# node_modules. After this, `make dev` (or `bash demo/scripts/run-backends.sh`
# + `cd front-app && npm run dev`) just works.
#
# Requires `uv` (https://docs.astral.sh/uv/) and `npm` on PATH.
#
#     bash demo/scripts/setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

command -v uv >/dev/null 2>&1 || {
  echo "error: 'uv' not found. Install it: https://docs.astral.sh/uv/" >&2
  exit 1
}
command -v npm >/dev/null 2>&1 || {
  echo "error: 'npm' not found. Install Node.js 18+: https://nodejs.org/" >&2
  exit 1
}

echo "→ proxy venv  (demo/proxy/.venv)"
[ -d demo/proxy/.venv ] || uv venv demo/proxy/.venv
# hexa-events is a local path dep of the proxy — install it editable first so
# the proxy's dependency resolves without hitting PyPI.
uv pip install --python demo/proxy/.venv -e demo/packages/hexa-events
uv pip install --python demo/proxy/.venv -e 'demo/proxy[dev]'

echo "→ agent-server venv  (demo/agent-server/.venv)"
[ -d demo/agent-server/.venv ] || uv venv demo/agent-server/.venv
# [llm] pulls openai (Probe) + google-genai (Orbit) for real model replies.
uv pip install --python demo/agent-server/.venv -e 'demo/agent-server[dev,llm]'

echo "→ custom-UI library  (custom-UI/dist via npm run build)"
# front-app imports from "agent-ui" via a file:../custom-UI link in its
# package.json. tsc resolves the import from custom-UI/dist/index.d.ts, so a
# clean clone must build the library before typechecking the front-app.
(cd custom-UI && npm install && npm run build)

echo "→ front-app dependencies  (front-app/node_modules)"
(cd front-app && npm install)

echo
echo "done. start the stack with:"
echo "    AGENT_ENABLE_LLM=1 bash demo/scripts/run-backends.sh"
echo
echo "Optional — HexGate-wrapped healthcare agent (set HEXGATE_KEY to enable):"
echo "  needs the hexgate checkout at ../hexgate and a Python >=3.13 venv, then:"
echo "    uv venv --python 3.13 demo/agent-server/.venv   # if the venv isn't already 3.13"
echo "    uv pip install --python demo/agent-server/.venv -e 'demo/agent-server[dev,llm,hexgate]'"
