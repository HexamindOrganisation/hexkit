#!/usr/bin/env bash
# Bootstrap the demo backend venvs from their pyprojects, so a fresh clone can
# run `run-backends.sh`. venvs are gitignored — this recreates them.
# Requires `uv` (https://docs.astral.sh/uv/). Run from the repo root under WSL:
#
#     bash demo/scripts/setup.sh
#
# Then:  AGENT_ENABLE_LLM=1 bash demo/scripts/run-backends.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

command -v uv >/dev/null 2>&1 || {
  echo "error: 'uv' not found. Install it: https://docs.astral.sh/uv/" >&2
  exit 1
}

echo "→ proxy venv  (demo/proxy/.venv)"
uv venv demo/proxy/.venv
# hexa-events is a local path dep of the proxy — install it editable first so
# the proxy's dependency resolves without hitting PyPI.
uv pip install --python demo/proxy/.venv -e demo/packages/hexa-events
uv pip install --python demo/proxy/.venv -e 'demo/proxy[dev]'

echo "→ agent-server venv  (demo/agent-server/.venv)"
uv venv demo/agent-server/.venv
# [llm] pulls openai (Probe) + google-genai (Orbit) for real model replies.
# NOTE: the `hexgate` extra is intentionally NOT installed here — it pulls a
# heavy, Python-3.13-only sibling SDK and would couple this setup to an external
# checkout. The plain healthcare path works without it; opt in separately (below).
uv pip install --python demo/agent-server/.venv -e 'demo/agent-server[dev,llm]'

echo
echo "done. start the stack with:"
echo "    AGENT_ENABLE_LLM=1 bash demo/scripts/run-backends.sh"
echo
echo "Optional — HexGate-wrapped healthcare agent (HEALTHCARE_HEXGATE=1):"
echo "  needs the hexgate checkout at ../hexgate and a Python >=3.13 venv, then:"
echo "    uv venv --python 3.13 demo/agent-server/.venv   # if the venv isn't already 3.13"
echo "    uv pip install --python demo/agent-server/.venv -e 'demo/agent-server[dev,llm,hexgate]'"
