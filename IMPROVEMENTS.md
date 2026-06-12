# Suggested Improvements

A pragmatic list of structural and setup improvements grouped by impact and effort. Pick the ones that match where the project is heading.

## TL;DR — the four biggest wins

1. **Add a top-level Makefile** so newcomers don't need to memorize `bash demo/scripts/run-backends.sh` and `cd front-app && npm run dev`. One `make dev` should bring everything up.
2. **Build `custom-UI` in `setup.sh`** — `front-app` depends on it as a `file:../` link and a clean clone currently fails `tsc --noEmit` until you manually build it.
3. **Wire CI** (GitHub Actions): lint + test + typecheck on every PR. The test suite already has gaps (see §1 below) that go unnoticed without CI.
4. **Move `demo/proxy` and `demo/agent-server` out of `demo/`.** The name suggests scaffolding, but these are the real platform backend and reference agent server. Rename to `services/` or `apps/`. `demo/` would then contain only `starter-agent` and `design/`.

---

## 1. Testing

### Gaps
- **No frontend tests.** `front-app/` has zero unit or integration tests. Add Vitest for component tests + a single Playwright happy-path test (login → send message → see reply).
- **No coverage reporting.** Add `pytest-cov` to dev deps and a `make coverage` target. A floor of ~80% on `platform_backend/auth/` and `routes/` would catch the kind of bug that `test_dev_seed.py` caught (dev password didn't satisfy schema).

### Existing test infrastructure is good
The session-scoped in-memory SQLite + per-test truncation in [conftest.py](demo/proxy/tests/conftest.py) is the right pattern — keep it. The 14 new auth-related tests added in this PR follow the same shape.

### Recommended additions
- **Frontend Vitest config** in [front-app/](front-app/). Add `vitest`, `@testing-library/react`, `@testing-library/jest-dom` to devDependencies and a `vitest.config.ts`. Start with three smoke tests: AuthContext storing/clearing token, RouteGuard redirecting, LoginPage submitting valid creds.
- **An end-to-end test against a real running stack.** Playwright + a `make e2e` target that spins up proxy + agent-server + front-app, runs one happy-path test, tears them down.
- **CI matrix** running tests on Python 3.11 and 3.12 (the [pyproject](demo/proxy/pyproject.toml) says `>=3.11`).

---

## 2. Setup & developer experience

### Friction points today
- **Manual `PYTHONPATH`.** Running tests requires `PYTHONPATH=src:../packages/hexa-events/src` — invisible to anyone who doesn't read [run-backends.sh](demo/scripts/run-backends.sh). Either move to a `src/`-layout where `pip install -e .` sets it, or document the env var in [pytest.ini](demo/proxy/pytest.ini) with `pythonpath = src ../packages/hexa-events/src`.
- **`custom-UI` build is not in setup.** `front-app` imports from `agent-ui` (a `file:../custom-UI` link). On a clean clone, `npm run dev` works (Vite is lenient) but `tsc --noEmit` fails with TS2307 "Cannot find module 'agent-ui'". Add `npm install && npm run build` for `custom-UI/` to [demo/scripts/setup.sh](demo/scripts/setup.sh).
- **Multi-terminal start.** Make `make dev` orchestrate proxy + agent-server + front-app with `concurrently` (npm) or a tmux/foreman-style runner. Bonus: prefix log lines with the service name.
- **No `.env.example`.** Document `PLATFORM_JWT_SECRET`, `PLATFORM_FERNET_KEY`, `PLATFORM_SEED_DEV_USER`, `AGENT_ENABLE_LLM` etc. in a checked-in `.env.example` so devs know what they can override.

### Recommended top-level layout
Add at repo root:
```
Makefile                    # see below
.github/workflows/ci.yml    # lint + test + typecheck
.editorconfig               # consistent whitespace across editors
.env.example                # documented overridable vars
```

### Sample Makefile

```makefile
.PHONY: setup dev test lint format typecheck

setup:
	bash demo/scripts/setup.sh
	cd custom-UI && npm install && npm run build
	cd front-app && npm install

dev:
	AGENT_ENABLE_LLM=1 bash demo/scripts/run-backends.sh &
	cd front-app && npm run dev

test:
	cd demo/proxy && PYTHONPATH=src:../packages/hexa-events/src .venv/bin/python -m pytest
	cd front-app && npm test  # once Vitest is wired

lint:
	cd demo/proxy && .venv/bin/ruff check .
	cd demo/agent-server && .venv/bin/ruff check .

format:
	cd demo/proxy && .venv/bin/ruff format .
	cd demo/agent-server && .venv/bin/ruff format .

typecheck:
	cd front-app && npx tsc --noEmit
```

---

## 3. Code quality

### Already added in this PR
- `ruff` is now a dev dependency in both Python packages with a sensible default config (lint rules: E/W/F/I/B/UP/C4/SIM).

### Still missing
- **Python type checking.** No `mypy` or `pyright` configured. The codebase is well-typed in practice — adding mypy with a permissive baseline (`--ignore-missing-imports --check-untyped-defs`) would catch real bugs cheaply.
- **Pre-commit hooks.** Add a [pre-commit](https://pre-commit.com/) config that runs `ruff check --fix`, `ruff format`, and `tsc --noEmit` on staged files. The PR-time cost of catching mistakes locally is far below catching them in CI.
- **No frontend linter.** ESLint is conspicuously absent. Add `eslint`, `@typescript-eslint/parser`, `eslint-plugin-react-hooks`.

---

## 4. Structure

### Misleading names
- **`demo/`** contains the actual platform backend ([demo/proxy/](demo/proxy/)) and a reference agent server ([demo/agent-server/](demo/agent-server/)) — the name suggests these are throwaway examples. Rename to `services/` or split:
  - `services/proxy/` (platform backend)
  - `services/agent-server/` (reference agent server)
  - `examples/starter-agent/` (the actual minimal template)
- **`legacy/`** ships with the repo but is reference-only. Move to a separate archive branch or `docs/legacy/`.
- **`custom-UI/`** is hyphenated; everything else in the repo uses underscores or single words. Rename to `agent-ui/` (matches the npm package name) or `custom_ui/`.

### File-level
- **`auth/implicit_user.py`** is now a dev-only seed helper, not a "single-user shim." Rename to `auth/dev_seed.py` to match its new purpose.
- **`routes/proxy.py`** clashes with the project being called "the proxy" — rename to `routes/agents.py` (it has `prefix="/agents"`).
- **`schemas/` and `models/` split** is good. Keep it.

### Hexa-events package
[demo/packages/hexa-events/](demo/packages/hexa-events/) is a path dependency consumed by the proxy. If it's stable, publish it to a private PyPI / GitHub Packages and pin a version. If it's not stable, document that it's coupled to `demo/proxy` and rename to `proxy/hexa_events/` so the boundary is clear.

---

## 5. Security

### Production blockers (cheap to fix)
- **JWT secret default of `"dev-only-change-me-dev-only-change-me"`** in [config.py](demo/proxy/src/platform_backend/config.py). Add a startup check: if `settings.jwt_secret` matches the default and `app.debug` is false, raise.
- **No rate limiting on `/auth/login`.** A botnet can brute-force any account with a weak password — the constant-time hash check makes per-request cost predictable, which is exactly what brute-force tools want. Add `slowapi` or similar.
- **JWT key length warning surfaces in tests.** `InsecureKeyLengthWarning: The HMAC key is 19 bytes long, which is below the minimum recommended length of 32 bytes for SHA256`. The dev default is 35 chars (fine) but the test secret in [conftest.py](demo/proxy/tests/conftest.py) isn't set. Add a 32+-byte test secret to the env-bootstrap section.

### Missing flows
- No password reset.
- No email verification.
- No refresh token — the 24h hard expiry means anyone using the app for >24h has to log in again every day.
- No logout-server-side. JWTs are stateless; for a real product you'd want an in-process token blocklist or shorter expiry + refresh tokens.

### Token storage
Tokens live in `localStorage`. XSS-vulnerable. For a production app, move to httpOnly cookies + CSRF tokens. The [client.ts](front-app/src/api/client.ts) docstring already notes this is a future migration path — the code is structured so it'd be a one-file change.

---

## 6. Documentation

### What exists
- [README.md](README.md) — high-level pitch.
- [QUICKSTART.md](QUICKSTART.md) — local run guide.
- [demo/README.md](demo/README.md), [custom-UI/README.md](custom-UI/README.md) — per-package docs.

### What's missing
- **`ARCHITECTURE.md`** at the root: how proxy ↔ agent-server ↔ frontend talk, the SSE event schema, the YAML UI contract.
- **`CONTRIBUTING.md`**: branch model, commit style, how to run tests/lint, how to add a new agent.
- **OpenAPI docs link.** FastAPI auto-generates them at `/docs` and `/redoc` — the README should call this out.
- **A `docs/` directory for the YAML widget reference.** The `custom-UI` library has 11 widgets but no centralized reference for what YAML they each consume.

---

## Prioritized roadmap

The first three items below were done in the recent setup pass — `make setup` builds custom-UI, `make dev` brings everything up, CI runs lint + test + typecheck on every push, and the proxy suite passes 95/95.

Next up:

1. **Frontend tests.** Vitest for AuthContext / RouteGuard / LoginPage smoke tests, then one Playwright happy-path test.
2. **Rename `demo/` → `services/`** — the proxy and agent-server are the real platform, not demos. Pure rename + path updates.
3. **ESLint + pre-commit hooks** for the JS side; mypy/pyright for the Python side.
4. **Security blockers** before this goes anywhere near production: rate limit on `/auth/login`, fail-loud check on the default JWT secret, refresh tokens.
