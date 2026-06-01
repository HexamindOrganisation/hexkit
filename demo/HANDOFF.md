# HexaUI — Implementation Handoff

> Working doc for resuming the HexaUI build. Read this top-to-bottom and you
> have everything needed to continue without re-exploring.
> Companion files: `demo/specs.md` (pivot vision), `demo/design_handoff_hexaui/`
> (design source of truth), approved plan at
> `~/.claude/plans/dapper-waddling-firefly.md`, memory at
> `~/.claude/projects/-mnt-c-Users-quent-Documents-custom-UI/memory/project-pivot-2026-05.md`.

---

## 1. What this project is (the pivot)

The repo was a **"unified agent runtime"**: a backend (`backend-runtime/`) that
wrapped LangChain/OpenAI/Google-ADK behind one protocol + normalized event
schema, a control-plane (`platform-backend/`), a YAML widget lib (`custom-UI/`),
and an end-user shell (`front-app/`).

**It is pivoting to UI/UX-first** (`demo/specs.md`). The framework-unifying
runtime is **dropped as a product**. Developers now build their **own streaming
backend** conforming to a **new, simpler contract**. The platform focuses on the
chat UX, conversation history, folders, encrypted secrets, and **proxying** to
the developer's backend.

The UX target is **HexaUI** (fully designed in `demo/design_handoff_hexaui/`): a
single chat platform hosting many agents, each configured in YAML on top of one
constant minimalist chrome (folding sidebar + top bar). Core design principle:
**the active agent's color is the only color in the product**, driven from one
variable (`page.main_color` → `--accent`). Conversation history + file tree are
**chrome, not widgets**.

Org is **hexamind.ai** (user: dev01@hexamind.ai). Product name: **HexaUI**.

---

## 2. Decisions locked with the user (do not re-litigate)

1. **Build fresh in `demo/`**, copying/adapting reusable parts from the old modules.
2. **Single-user for now.** Keep salvageable auth/crypto; collapse to ONE implicit
   user; keep DB columns (`user_id`) so multi-user can return later.
3. **New, simpler streaming contract** between proxy and developer backend
   (do NOT reuse the old contract verbatim). Reuse only the event-schema + emitter.
4. **Use `custom-UI` in place** (keep its location) and **redesign its widget
   components** to match the design handoff (theme bridge + widget restyle live
   INSIDE `custom-UI/`).
5. **Build a reference agent-server** in `demo/` as the contract's executable spec.
6. **First milestone = contract + proxy** (backend-solid before UI polish).

---

## 3. Target layout

```
demo/
  specs.md                      # (exists) the pivot vision
  design_handoff_hexaui/        # (exists) HexaUI design source of truth
  HANDOFF.md                    # (this file)
  CONTRACT.md                   # TODO (M1c) — the streaming contract spec
  packages/hexa-events/         # IN PROGRESS (M1a) — Python event-schema lib
  agent-server/                 # TODO (M1b) — reference developer backend
  proxy/                        # TODO (M1d) — platform backend, slimmed single-user
  web/                          # TODO (M3) — front-app HexaUI shell (depends on custom-UI)
custom-UI/                      # (in place) theme bridge + widget redesign happen HERE (M2)
```

---

## 4. The streaming contract — **DESIGN B / framework-tagged** (full spec in `demo/CONTRACT.md`)

> **Decision (locked with user, supersedes earlier revisions):** the dev changes
> **no agent code** — only a thin server layer that **forwards their framework's
> native events, tagged with the framework**. The **proxy translates** per
> framework into the one unified internal schema. Reuses the existing
> `backend-runtime` adapters' mapping logic (lifted into proxy-side, wire-driven
> translators — the proxy imports no framework libs). `native` is the escape
> hatch for custom loops / unsupported frameworks. Rationale: least dev friction
> for someone already on a supported framework.

Two layers:
- **Developer contract (imposed):** the 5 endpoints below + each stream frame
  tagged `{framework, event}`.
- **Internal hexa schema (proxy↔frontend):** produced by the proxy via
  `hexa-events` `RunEmitter`; consumed by `front-app` `runtimeBridge.ts`.

Endpoints (proxy calls these): unchanged — `GET /agents`, `GET /agents/{id}/ui`,
`POST /agents/{id}/stream`, `POST /agents/{id}/cancel`, `POST /agents/{id}/actions/{name}`.

**Stream request body** (proxy → backend): `{run_id, input:{messages}, context:{conversation_id, credentials}}` (no `user_id` — single-user).

**Stream frames** (backend → proxy), one per SSE `data:`:
```
data: {"framework":"<name>","event":<framework-native event, JSON-projected>}
```
Backend does **NOT** emit run envelope — proxy synthesizes `run_start`/`run_end`.

**Supported `framework` → translator** (`demo/proxy/.../translators/`):
- `langchain`/`langgraph`/`deepagents` → `astream_events(v2)` events
- `openai-agents` → `Runner.run_streamed().stream_events()` items
- `google-adk` → `Runner.run_async()` `Event`s
- `native` → already-normalized minimal events (`text`/`reasoning`/`tool`/`tool_result`/`error`/`done`)

Translators ported from `backend-runtime/.../adapters/{langchain,openai_agents,
google_adk}_adapter.py` (the event→`RunEmitter` mapping; chain/state/trace and
approval bits dropped). All emit `widget="tool-calls"` for tool calls.

**Proxy flow** (`demo/proxy/.../routes/chat.py`): `run_start` → per frame, select
translator by `framework` (first frame) → `translator.handle(emitter, event)` →
`run_end` at EOF. Frames each rich event with `to_sse_frame`, pipes to browser,
persists accumulated final message.

**Internal hexa schema** (unchanged): `run_start`, `block_*` (text + reasoning),
`tool_*` (+ optional `widget`), `run_end`, `error`. Consumed by `front-app`
`runtimeBridge.ts` (`block_delta`→token, `block_end`→message,
tool→tool-call(widget), run_*→status).

---

## 5. Exploration findings — what's reusable (verified, with paths)

### `custom-UI/` (React+TS+shadcn/Tailwind YAML widget lib) — READY, minor work
- Genuinely **chromeless**: `<AgentUI>` (`custom-UI/src/components/AgentUI.tsx:20-30`)
  renders only a MAIN region + footer slot. A host shell wraps it directly.
- **All 13 widgets already exist** (`custom-UI/src/widgets/`): ai-chat-input,
  ai-response, ai-history, button-group, file-tree, form, markdown, metrics,
  page-footer, page-header, placeholder, spacer, table, tool-calls.
- A **single-accent bridge already exists**: `page.theme.accent` →
  `--primary`/`--ring` (`custom-UI/src/compile/theme.ts:8-18,82-101`,
  `schema/page.ts:12-37`). M2 extends this to the full HexaUI token scale +
  `page.main_color`.
- Runtime contracts: `AgentBridge` (`runtime/agentBridge.ts:1-16`),
  `ActionDispatcher` (`runtime/dispatcher.ts:1-10`), hooks `useWidgetData`/
  `useAgentInbox`/`useConversation`/`useAgentUIContext` (`runtime/context.tsx`).
- Tool-calls route to widgets BY NAME via `useAgentInbox()` + the `widget` field.

### `front-app/` (React+TS+Vite shell, mid-rewrite) — ~65% reusable
- **KEEP as-is** (zero UI coupling): `runtime/sseStream.ts`, `runtime/types.ts`,
  `runtime/runtimeBridge.ts`, `runtime/api.ts`. `runtimeBridge` already translates
  the StreamEvent schema → custom-UI AgentBridge events (token/message/status/
  tool-call/error). `types.ts` mirrors the Python event schema.
- **KEEP** api client: `api/client.ts` (authed fetch + JWT, drop 401 hard-nav for
  single-user), `api/agents.ts`, `api/conversations.ts`.
- **DELETE** for single-user: `auth/*`, `pages/LoginPage.tsx`, `pages/SignupPage.tsx`,
  `api/auth.ts`. Keep keys UI as Settings (secrets are real).
- **REBUILD** to HexaUI: `layout/{AppShell,Header,Sidebar}`, `pages/ChatPage.tsx`
  (currently a stub — never mounts `<AgentUI>`!), `components/AgentDropdown`.
- Vite proxy `/api/*` → `PLATFORM_BACKEND_URL` (default `http://127.0.0.1:8000`),
  `front-app/vite.config.ts`. Deps: React 18, React Router 6, @tanstack/react-query,
  lucide-react, agent-ui (local link), tailwind.

### `platform-backend/` (FastAPI + SQLAlchemy async + Postgres + Alembic) — slim cleanly
- Reusable as-is: SSE passthrough + tee-parse (`routes/chat.py:146-219`, `sse.py`),
  Fernet secret encryption (`crypto/fernet.py`), conversation/folder/message
  persistence, conversation auto-titling.
- Coupling to the OLD runtime is isolated to 3 spots:
  - `routes/chat.py:134-142` — the `runtime_body` shape (drop `user_id`).
  - `runtime_client.py:31` (URL), `:97-100` (cancel path/body), `:71-83`
    (metadata/tools/health — delete).
  - `routes/proxy.py:26-41` — metadata/tools/health passthrough (delete; keep
    `GET /agents` `:21-23` and `/agents/:id/ui` `:44-51`).
- Models (`models/`): User(id,email,password_hash), ApiKey(user_id,provider,
  ciphertext, unique(user_id,provider)), Folder(user_id,name), Conversation(
  user_id,folder_id,agent_id,title,updated_at), Message(conversation_id,role,
  content,run_id). 3 Alembic migrations.
- `routes/me_keys.py:95-106` `load_credentials_dict(session, user_id)` →
  `{"openai_api_key":..., ...}` — used by chat.py, UNCHANGED.
- Auth: `auth/{jwt,passwords,deps}.py`, `current_user` dependency in `deps.py`.
- Config `config.py:37-40`: `runtime_url` (default `http://127.0.0.1:8080`),
  `jwt_secret`, `fernet_key`, `database_url`. Env prefix `PLATFORM_*`.

### `backend-runtime/` (DROPPED as product; salvage 2 files)
- `src/platform_runtime/events.py` (~400 lines, ZERO imports) — framework-agnostic
  Pydantic event schema. Lift + trim → `hexa_events/events.py`.
- `src/platform_runtime/run_emitter.py` (~390 lines) — `RunEmitter` emit-side
  helper (sequence numbering, block lifecycle, step accumulation). Lift + trim.
- `src/platform_runtime/server/app.py:258-270` `_to_sse_frame` — the SSE
  serialization. Lift → `hexa_events/sse.py` (emit raw bytes).

---

## 6. Milestone plan

- **M1 (CURRENT) — Contract + events lib + reference backend + proxy.** Curl-testable,
  no frontend. Sub-tasks M1a–M1d below.
- **M2 — `custom-UI` theme bridge + widget redesign.** Parallelizable with M1.
  Port HexaUI tokens from `design_handoff_hexaui/{theme,widgets}.css` into
  `custom-UI/src/{shadcn.css,styles.css}`; `page.main_color` → `--accent` in
  `compile/theme.ts`+`schema/page.ts`; restyle widgets; drop `page-header`.
- **M3 — `demo/web` HexaUI shell.** Copy front-app; keep runtime/+api; single-user
  auto-init; build chrome (folding sidebar w/ shared cross-agent history + colored
  glyphs + file tree, top-bar agent picker, composer) wrapping `<AgentUI>`;
  ChatPage mounts `<AgentUI>` with runtimeBridge; `page.main_color` drives theme.
- **M4 — E2E + polish.** Wire web→proxy→agent-server; motion (bloom/settle/caret/
  thinking metaball); mobile collapse; conversation/folder management UI.

---

## 7. M1 sub-tasks — exact build instructions

> ⚠️ **HISTORICAL — superseded by §4/§8.** This section describes the original
> design where the dev backend emitted the rich hexa schema directly. M1 was
> reworked to **design B** (dev emits minimal events, proxy normalizes). M1 is
> DONE per §8; read §4 for the actual contract. `hexa-events` is now
> proxy-internal; the agent-server emits minimal events (no `RunEmitter`); the
> proxy gained `translate.py`. Kept for archaeology only.

### M1a — `demo/packages/hexa-events/`
Standalone installable Python package; depended on by agent-server AND proxy via
`file:` path install so the schema can't drift.

Files to create:
- `pyproject.toml` — name `hexa-events`, package `hexa_events`, dep `pydantic>=2`,
  src layout (`src/hexa_events/`). Build backend hatchling or setuptools.
- `src/hexa_events/events.py` — **lift from** `backend-runtime/.../events.py`, and:
  - DELETE: `TraceSpanEvent`, `StateUpdateEvent`, `ApprovalRequestedEvent`,
    `ApprovalResolvedEvent`, `ApprovalSource/Kind/Decision`, their `EventType`
    members (TRACE_SPAN, STATE_UPDATE, APPROVAL_*), and their union members.
  - ADD `widget: str | None = None` to `ToolStartEvent`/`ToolUpdateEvent`/`ToolEndEvent`.
  - Drop the `RuntimeEvent = StreamEvent` alias; rewrite docstring (no "Fortify").
  - Keep RunNode, BaseStreamEvent, block model, BlockType, ToolCallState, Step
    models, AgentRunResult.
  - **STATUS: this file's content was fully drafted (see the Write that was
    interrupted) — re-create it from the spec above. The drafted version is correct.**
- `src/hexa_events/run_emitter.py` — **lift from** `backend-runtime/.../run_emitter.py`, and:
  - Remove imports of TraceSpanEvent/StateUpdateEvent/Approval* and the methods
    `state_update`, `trace_span`, `approval_requested`, `approval_resolved`
    (`run_emitter.py:302-389`).
  - ADD a `widget: str | None = None` kwarg to `tool_start` and `tool_end`; thread
    it into the emitted ToolStartEvent/ToolEndEvent.
  - Keep everything else (extract_query, summarize_output, block lifecycle).
- `src/hexa_events/sse.py` — `to_sse_frame(event: StreamEvent) -> bytes` emitting
  exactly `b"event: {type}\nid: {event_id}\ndata: {compact_json}\n\n"` (matches
  `_to_sse_frame` at `app.py:258-270` + the parser `platform-backend/.../sse.py`).
  Use `event.model_dump(mode="json")` + `json.dumps(..., separators=(",",":"))`.
- `src/hexa_events/__init__.py` — export `RunEmitter`, `StreamEvent`, `EventType`,
  the event classes, `to_sse_frame`, `extract_query`, `summarize_output`.

### M1b — `demo/agent-server/` (reference developer backend)
FastAPI app, the executable spec. Layout:
```
demo/agent-server/
  pyproject.toml          # deps: fastapi, uvicorn, sse-starlette OR plain StreamingResponse,
                          #       hexa-events (file:../packages/hexa-events), pyyaml, openai (optional)
  src/agent_server/
    __main__.py           # uvicorn entry; AGENT_* env (host/port, default :8080)
    config.py
    server/app.py         # create_app(); lifespan holds an in-memory run registry for cancel
    roster.py             # AGENTS seed: Probe #3f9d94 (Research & retrieval),
                          #   Atlas #4f74c9 (Operations copilot), Forge #56809e (Code & build)
    ui/probe.yaml         # page.main_color + ai-response + tool-calls(id=tool-calls,title="Sources")
    ui/atlas.yaml         # metrics strip + ai-response + tool-calls
    ui/forge.yaml         # file-tree-driven coding layout (can be minimal)
    agents/base.py        # async run(input, context, emitter) -> async-iterator[StreamEvent]
    agents/echo.py        # echoes last user message, word-chunked via emitter.text_delta
    agents/llm.py         # optional OpenAI using context["credentials"]["openai_api_key"];
                          #   falls back to echo when absent (exercises secret forwarding)
    tools.py              # 1-2 fake tools (search/fetch) returning canned output
    routes/agents.py      # GET /agents, GET /agents/{id}/ui, POST stream, POST cancel, POST actions
```
- Stream endpoint: build `RunEmitter(run_id, agent_id=id)`; register run_id→task
  for cancel; emit `run_start` (use `extract_query(input)`); echo text via
  `text_delta`; emit a sample `tool_start(...widget="tool-calls")` +
  `tool_end(...widget="tool-calls")`; `run_end`; frame each via `to_sse_frame`;
  return `StreamingResponse(media_type="text/event-stream")`. On
  `asyncio.CancelledError`, stop. Add a per-chunk `await asyncio.sleep(...)` so
  cancel is testable.
- To prove secret forwarding, have echo prefix reply with
  `creds-present:{bool}` based on `context["credentials"].get("openai_api_key")`.

### M1c — `demo/CONTRACT.md`
Write the full contract (section 4 above expanded): endpoints, request body, SSE
framing, event schema (kept core + `widget`), roster shape, ui.yaml envelope
(`page.main_color` + `widgets`), credential forwarding, cancel, widget-targeted
tool-calls. The agent-server is the executable reference for it.

### M1d — `demo/proxy/` (copy `platform-backend/`, KEEP package name `platform_backend`)
Copy wholesale, then targeted changes:
- **Single-user:** add `auth/implicit_user.py` with `IMPLICIT_USER_ID`
  (`00000000-0000-0000-0000-000000000001`) + `async def current_user(session)`
  that loads that user. Swap the `from ..auth.deps import current_user` import in
  `routes/{me,me_keys,folders,conversations,chat,proxy}.py` to the implicit
  provider (route bodies UNCHANGED — they still filter by `user.id`). Seed the
  implicit user idempotently (`INSERT ... ON CONFLICT DO NOTHING`,
  email=`dev01@hexamind.ai`) in `server/app.py` lifespan after `init_engine()`.
  Remove the auth router include (`server/app.py:42`); leave `auth/{jwt,passwords,
  deps}.py` files on disk unwired.
- **Repoint:** `config.py` rename `runtime_url` → `agent_backend_url` (env
  `PLATFORM_AGENT_BACKEND_URL`, default `http://127.0.0.1:8080`); update reader in
  `runtime_client.py:31`.
- **`runtime_client.py`:** keep `stream`/`list_agents`/`get_ui_yaml`; change
  `cancel` (`:97-100`) to `POST /agents/{id}/cancel` body `{"run_id": run_id}`;
  delete `get_metadata`/`get_tools`/`get_health` (`:71-83`).
- **`routes/proxy.py`:** keep `GET /agents` + `/agents/{id}/ui`; delete
  metadata/tools/health routes.
- **`routes/chat.py`:** change `runtime_body` (`:134-142`) to the v1 shape (drop
  `user_id` from context). Accumulator (`:146-219`) + persistence UNCHANGED (event
  + field names preserved; `widget` passes through). Verify `etype` check at `:174`.
- **Alembic:** NO new migrations (keep `user_id` columns; implicit user seeded at
  runtime, not in a migration). Port `alembic/` + `alembic.ini` unchanged.
- **Tests:** `tests/` use bearer tokens; swap the auth helper to no-auth/implicit.
  `test_auth.py` becomes irrelevant. Not M1-blocking but do it.

### M1 verification (curl, no frontend)
1. Postgres: `docker run -e POSTGRES_USER=platform -e POSTGRES_PASSWORD=platform
   -e POSTGRES_DB=platform -p 5432:5432 postgres`; then `alembic upgrade head` in proxy.
2. agent-server: `python -m agent_server` on `:8080`.
3. proxy: `PLATFORM_AGENT_BACKEND_URL=http://127.0.0.1:8080 PLATFORM_FERNET_KEY=<key>
   python -m platform_backend` on `:8000` (lifespan seeds implicit user).
Checks (NO Authorization header):
- `curl :8000/agents` → array with `main_color`. `curl :8000/agents/probe/ui` →
  `text/yaml` with `page.main_color: "#3f9d94"`.
- `curl -X PUT :8000/me/keys/openai -d '{"value":"sk-test"}' -H 'content-type: application/json'`
  → 204; `curl :8000/me/keys` → present.
- `curl -X POST :8000/conversations -d '{"agent_id":"probe"}' -H 'content-type: application/json'`
  → conversation id.
- `curl -N -X POST :8000/conversations/{id}/messages -d '{"content":"hello"}' -H 'content-type: application/json'`
  → SSE: `run_start`, `block_*`(text), `tool_start`+`tool_end` with
  `"widget":"tool-calls"`, `run_end`.
- `curl :8000/conversations/{id}/messages` → user + assistant (joined text, run_id),
  auto-titled, updated_at bumped. Assistant text shows `creds-present:true`.
- Cancel: long stream + `curl -X POST :8000/conversations/{id}/cancel` →
  `{cancelled:true}`; partial text persisted.

---

## 8. Current status (as of 2026-06-01)

- ✅ Exploration complete (all 4 modules mapped — section 5).
- ✅ **M1 COMPLETE + verified, reworked to DESIGN B (§4).** Backend contract is
  solid; no frontend yet. **Design B = dev backend emits minimal events; proxy
  normalizes to the rich hexa schema.**
  - ✅ **`demo/packages/hexa-events/`** — the rich internal schema + `RunEmitter`
    + `to_sse_frame`. **Now proxy-internal** (proxy↔frontend); the dev backend no
    longer depends on it. Unchanged since M1a (trimmed schema, `widget` on tool
    events).
  - ✅ **`demo/agent-server/`** (reference dev backend) — each agent declares a
    `framework` and yields that framework's **native events**; the route wraps
    each as `{"framework", "event"}` and frames to SSE. `protocol.py` (native
    builders + `to_sse` + `last_user_text`); `EchoAgent`/`LLMAgent` = `native`;
    `agents/demos.py` = `LangChainDemoAgent`/`OpenAIAgentsDemoAgent`/
    `GoogleADKDemoAgent` (emit canned native shapes); `agents/select.py` picks by
    roster `framework`. Roster now **4 agents**: probe=native, atlas=langchain,
    forge=openai-agents, orbit=google-adk (+ `ui/orbit.yaml`, color #b0714f).
    Entry: `python -m agent_server`.
  - ✅ **`demo/CONTRACT.md`** — rewritten: API shape + `{framework, event}`
    frames; §6 lists supported frameworks + native shapes + serialize note.
  - ✅ **`demo/proxy/`** (copied from `platform-backend`, package still
    `platform_backend`): single-user via `auth/implicit_user.py`;
    `config.runtime_url`→`agent_backend_url`; `runtime_client.cancel`→
    `POST /agents/{id}/cancel {run_id}`, metadata/tools/health deleted;
    `routes/proxy.py` trimmed. **Translators (design B):**
    `translators/{base,native,langchain,openai_agents,google_adk}.py` + registry
    `__init__.get_translator(framework)`; **no framework libs imported** — pure
    dict pattern-match on serialized native events, driving a shared `RunEmitter`.
    Ported from `backend-runtime/.../adapters/*`. `routes/chat.py` routes each
    `{framework,event}` frame to the selected translator; synthesizes run_start/
    run_end; persists final message. Depends on `hexa-events`. Alembic unchanged.
    (Old single-format `translate.py` removed.)
  - ✅ **Verification** — `demo/scripts/e2e_check.py` (in-process, **all 4
    frameworks**: each agent's native stream → its translator → identical rich
    hexa schema → SQLite; 19 checks pass) and `demo/scripts/cancel_check.py`
    (mid-stream cancel, live socket; passes). See `demo/scripts/README.md`.

**Gaps deferred (not M1-blocking):**
- Postgres + Alembic path not run (used SQLite + `create_all` for the e2e —
  same models, the dialect the repo's tests already use). Run `alembic upgrade
  head` against Postgres before M4 e2e.
- `demo/proxy/tests/` still use bearer tokens (`test_auth.py` now irrelevant) —
  swap the auth helper to no-auth/implicit. Not done yet.
- venv strategy for `demo/` not finalized (uv recommended; e2e ran via the
  existing `platform-backend/.venv` + `backend-runtime/.venv` with PYTHONPATH).

**Next action:** **M2** (`custom-UI` theme bridge + widget redesign) and/or
**M3** (`demo/web` HexaUI shell) — see section 6. M2 and M3 are the remaining
build; M1 backend is done.

---

## 9. Gotchas / notes

- Keep the proxy Python package named `platform_backend` to avoid a huge import
  diff; only the conceptual rename (`runtime_url`→`agent_backend_url`) matters.
- Implicit-user seed must be an idempotent upsert (concurrent workers).
- agent-server framing: if using plain `StreamingResponse`, `to_sse_frame` must
  emit raw bytes ending in `\n\n`; if using `sse-starlette`, it wants a dict
  `{event,id,data}`. Keep ONE framing path in `hexa-events` — recommend raw bytes
  + `StreamingResponse` (simplest, matches the proxy parser exactly).
- The proxy's chat accumulator only tracks TEXT blocks for persistence; tool
  `widget` field is ignored there and passed through on the wire — correct.
- `.venv` dirs exist at repo root and per-module; there's a venv in
  `backend-runtime/`, `platform-backend/`, root. Decide venv strategy for the new
  `demo/` packages (uv recommended).
