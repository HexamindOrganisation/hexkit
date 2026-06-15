# HexaUI dev Makefile — see QUICKSTART.md for prerequisites (uv + Node 18+).
#
# Common flow on a fresh clone:
#
#     make demo     # brand-new user: setup → register agents on HexGate → run, one command
#     make setup    # one-time: Python venvs, custom-UI build, front-app npm install
#     make dev      # backends + frontend in one terminal (Ctrl-C tears down both)
#
# Individual targets are listed in `make help`.

.PHONY: help setup backends frontend dev demo register install-hexgate \
        check test lint format typecheck \
        clean clean-venvs clean-node

# -- shared paths -----------------------------------------------------------
PROXY_PY      := proxy-server/.venv/bin/python
PROXY_PATH    := proxy-server/src:packages/hexa-events/src
AGENT_PY      := demo/agent-server/.venv/bin/python
AGENT_PATH    := demo/agent-server/src
HEXGATE       := demo/agent-server/.venv/bin/hexgate

# -- meta -------------------------------------------------------------------
help: ## Print this help.
	@awk 'BEGIN{FS=":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} \
	/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# -- setup ------------------------------------------------------------------
setup: ## Bootstrap a fresh clone: venvs, custom-UI build, front-app npm install.
	bash demo/scripts/setup.sh

# -- run --------------------------------------------------------------------
backends: ## Start agent-server (:8880) + proxy (:8800). Foreground; Ctrl-C stops both.
	bash demo/scripts/run-backends.sh

frontend: ## Start the Vite dev server (:8873).
	cd front-app && npm run dev

dev: ## Backends + frontend together. Ctrl-C tears down both.
	@trap 'kill 0' EXIT INT TERM; \
	 bash demo/scripts/run-backends.sh & \
	 cd front-app && npm run dev

demo: ## Brand-new user, one command: setup → register agents on HexGate → run everything (real LLM replies on; add your provider key in the UI under Settings → Keys).
	$(MAKE) setup
	$(MAKE) register
	AGENT_ENABLE_LLM=1 $(MAKE) dev

# -- hexgate ----------------------------------------------------------------
install-hexgate: ## Ensure the agent-server venv is Python 3.13 with the hexgate extra (idempotent).
	@if ! $(AGENT_PY) -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 13) else 1)' 2>/dev/null; then \
	   echo "→ (re)creating agent-server venv on Python 3.13 (hexgate needs >=3.13)"; \
	   uv venv --python 3.13 demo/agent-server/.venv; fi
	@$(AGENT_PY) -c 'import hexgate' 2>/dev/null || \
	   uv pip install --python demo/agent-server/.venv -e 'demo/agent-server[dev,llm,hexgate]'

register: install-hexgate ## Register the healthcare + devops agents on the HexGate platform (reads HEXGATE_KEY from demo/agent-server/.env).
	@if [ -f demo/agent-server/.env ]; then set -a; . demo/agent-server/.env; set +a; fi; \
	 if [ -z "$$HEXGATE_KEY" ]; then \
	   echo "HEXGATE_KEY not set — add it to demo/agent-server/.env or export it."; exit 1; fi; \
	 echo "→ registering healthcare_agent"; \
	 PYTHONPATH=$(AGENT_PATH) $(HEXGATE) register --agent agent_server.agents.healthcare_agent:agent && \
	 echo "→ registering devops_agent" && \
	 PYTHONPATH=$(AGENT_PATH) $(HEXGATE) register --agent agent_server.agents.devops_agent:agent

# -- test -------------------------------------------------------------------
test: ## Run the proxy test suite.
	cd proxy-server && PYTHONPATH=$(PROXY_PATH) .venv/bin/python -m pytest

# -- lint / format ----------------------------------------------------------
lint: ## ruff check across every Python package in the repo (shared ruff.toml).
	proxy-server/.venv/bin/ruff check .

format: ## ruff format across every Python package.
	proxy-server/.venv/bin/ruff format .

typecheck: ## tsc --noEmit on custom-UI and front-app.
	cd custom-UI && npm run typecheck
	cd front-app && npx tsc --noEmit

check: lint test typecheck ## Run lint + test + typecheck — the same gates CI enforces.

# -- clean ------------------------------------------------------------------
clean: clean-venvs clean-node ## Remove all generated artifacts.

clean-venvs: ## Remove Python virtual environments.
	rm -rf proxy-server/.venv demo/agent-server/.venv

clean-node: ## Remove node_modules + custom-UI build output.
	rm -rf custom-UI/node_modules custom-UI/dist front-app/node_modules
