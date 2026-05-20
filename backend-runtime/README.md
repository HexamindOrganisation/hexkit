# platform-runtime

The execution plane of the [Unified AI Agent Platform](../README.md).

A framework-agnostic HTTP server that wraps heterogeneous AI agent
frameworks (LangChain, OpenAI Agents SDK, Google ADK, …) behind a single
HTTP + SSE API and a normalized event schema. Agents written in any
supported framework are served identically: same routes, same event
stream, same UI.

**Status: v0.** Core, isolation, three framework adapters (with
LangGraph/DeepAgents aliasing), cancel API, and per-agent UI YAML
endpoint are shipped. Control-plane integration (auth, tenants,
persistence, secrets store) is owned by a separate service that does
not yet exist.

```
HTTP/SSE  ─►  FastAPI server  ─►  Registry  ─►  Adapter  ─►  Framework SDK
                                                  │
                                          (in-process or
                                       per-agent subprocess
                                          with own venv)
```

---

## Contents

- [Install](#install)
- [Quick start](#quick-start)
- [HTTP API](#http-api)
- [Event schema](#event-schema)
- [Writing an agent](#writing-an-agent)
- [Supported frameworks](#supported-frameworks)
- [Isolation modes](#isolation-modes)
- [Configuration](#configuration)
- [Writing a new adapter](#writing-a-new-adapter)
- [Testing](#testing)
- [Architecture](#architecture)
- [Limitations and roadmap](#limitations-and-roadmap)

---

## Install

Python 3.11+ required. Pick the framework extras you need:

```bash
pip install -e '.[langchain]'              # LangChain only
pip install -e '.[openai-agents]'          # OpenAI Agents SDK only
pip install -e '.[google-adk]'             # Google ADK only
pip install -e '.[langchain,openai-agents,google-adk]'   # all
```

Provider SDKs (OpenAI, Anthropic, Google) are **not** bundled. Install
them yourself based on which models your agents use:

```bash
pip install langchain-openai           # for LangChain + OpenAI
```

Optional: install [`uv`](https://github.com/astral-sh/uv) for ~10× faster
per-agent venv builds in subprocess mode.

---

## Quick start

The runtime serves a *directory of agents* — one subfolder per agent,
each with an `agent.yaml`. The bundled `examples/` directory has three
ready-to-run agents.

```bash
export OPENAI_API_KEY=...
export PLATFORM_AGENTS_DIR=examples
python -m platform_runtime
```

Server starts on `http://127.0.0.1:8080`. In another terminal:

```bash
# list loaded agents
curl http://127.0.0.1:8080/agents

# stream a run (SSE)
curl -N -X POST http://127.0.0.1:8080/agents/langchain-hello/stream \
  -H 'Content-Type: application/json' \
  -d '{"input": {"messages": [{"role":"user","content":"What time is it?"}]}}'
```

You will see a typed SSE stream:

```
event: run.started
event: message.delta       (×N — token stream)
event: tool.start          (name: get_current_time)
event: tool.end
event: message.delta       (×N — final answer)
event: message.completed
event: run.completed
```

---

## HTTP API

Every route is scoped under `/agents/{agent_id}`. Bodies are JSON;
responses are JSON for unary calls and `text/event-stream` for streams.

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET` | `/agents` | — | `AgentMetadata[]` |
| `GET` | `/agents/{id}/metadata` | — | `AgentMetadata` |
| `GET` | `/agents/{id}/tools` | — | `ToolDescriptor[]` |
| `GET` | `/agents/{id}/health` | — | `HealthStatus` (200 ok, 503 unhealthy) |
| `GET` | `/agents/{id}/ui` | — | Raw YAML (`text/yaml`) — agent-supplied UI definition, or `404` if absent |
| `POST` | `/agents/{id}/invoke` | `InvokeRequest` | `RunCompleted` (drains the stream) |
| `POST` | `/agents/{id}/stream` | `InvokeRequest` | SSE stream of `RuntimeEvent` |
| `POST` | `/agents/{id}/runs/{run_id}/cancel` | — | `{ "cancelled": bool }` — idempotent |

### `InvokeRequest`

```json
{
  "input": <any>,                       // adapter-specific; passed through
  "run_id": "<corr-id, optional>",      // generated if omitted
  "context": { "user_id": "u1", ... }   // platform-level metadata
}
```

The `input` shape is framework-specific by design:

- LangChain: `{"messages": [{"role":"user","content":"..."}]}` for
  `create_agent`, or whatever the chain expects.
- OpenAI Agents SDK: a raw string or list of input items.
- Google ADK: a string, or `{"input": "..."}`, or a `Content` instance.

The adapter is responsible for translating; the platform standardizes
*events*, not *inputs*.

### SSE frame shape

Each SSE frame carries the platform event type as the SSE `event` name,
the event id as the SSE `id` (usable as `Last-Event-ID` for reconnect),
and the full event payload as JSON:

```
event: message.delta
id:    a1b2c3...
data:  {"id":"...","run_id":"...","ts":"...","seq":3,
        "type":"message.delta","message_id":"...","delta":"hello"}
```

---

## Event schema

The closed set of normalized events. Every adapter speaks this vocabulary;
the UI consumes it framework-blind.

| Type | Emitted when | Key fields |
|---|---|---|
| `run.started` | First event of every run. | `agent_id`, `input` |
| `message.delta` | Streaming assistant text chunk. | `message_id`, `delta` |
| `message.completed` | Final form of a message. | `message_id`, `role`, `content` |
| `tool.start` | Tool invocation begins. | `tool_call_id`, `name`, `arguments` |
| `tool.end` | Tool invocation returns. | `tool_call_id`, `name`, `output` |
| `state.update` | Agent state changed (e.g. multi-agent handoff). | `key`, `value` |
| `trace.span` | A traced span finished. | `span_id`, `parent_span_id`, `name`, `start_ts`, `end_ts` |
| `approval.requested` | HITL pause requested. | `approval_id`, `reason`, `payload` |
| `error` | Recoverable or fatal error during the run. | `message`, `recoverable`, `details` |
| `run.completed` | Last event of every run. | `agent_id`, `output` |

Every event carries common envelope fields:

- `id` — unique event id (used as SSE `id`)
- `run_id` — groups events from one invocation
- `seq` — monotonic per-run counter starting at 0
- `ts` — ISO-8601 server timestamp
- `type` — discriminator

The full Pydantic schema lives in
[`events.py`](src/platform_runtime/events.py).

---

## Writing an agent

An agent is a folder with two files. The runtime discovers it via
`PLATFORM_AGENTS_DIR`.

### `agent.yaml`

```yaml
agent_id: my-agent          # URL slug; alphanumerics + - + _
name: My Agent
framework: langchain         # one of: langchain | openai-agents | google-adk
entrypoint: agent.py         # relative to this manifest
agent_callable: build_agent  # function name in entrypoint
version: 0.1.0

capabilities:
  streaming: true
  tools: true
  state: false
  approvals: false
  multi_turn: true

requirements:                # optional; installs into a per-agent venv
  - rich>=13

env:                         # declared env-var dependencies (informational)
  - OPENAI_API_KEY

extra:                       # adapter-/agent-specific; not platform schema
  model: gpt-4o-mini
```

Validation runs at load time: unknown frameworks, malformed `agent_id`,
missing entrypoint files, and YAML errors all fail with explicit messages
that point at the manifest.

### `agent.py`

A factory callable named in `agent_callable` returns a framework-native
object. The platform handles streaming, isolation, and events; you write
idiomatic framework code:

```python
# LangChain example
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

@tool
def get_time() -> str:
    """Returns current time."""
    return "..."

def build_agent():
    return create_agent(
        model=ChatOpenAI(model="gpt-4o-mini", streaming=True),
        tools=[get_time],
        system_prompt="You are concise.",
    )
```

### Multi-file agents

Both layouts work; both are tested.

**Flat layout** — siblings in the manifest dir:
```
my-agent/
  agent.yaml          (entrypoint: agent.py)
  agent.py            (does `from helpers import foo`)
  helpers.py
```

**Package layout** — entrypoint in a subfolder:
```
my-agent/
  agent.yaml          (entrypoint: app/main.py)
  app/
    __init__.py
    main.py           (does `from app.tools import x` OR `from tools import x`)
    tools.py
```

Internally the runtime adds **both** the manifest dir and the entrypoint's
own dir to `sys.path`, so package-rooted and script-style sibling imports
both resolve.

---

## Supported frameworks

| Manifest `framework:` | Min version | Entrypoint returns | Example |
|---|---|---|---|
| `langchain` | 1.0 | LCEL `Runnable` or `create_agent` result | [examples/langchain_hello](examples/langchain_hello) |
| `langgraph` | (langchain ≥ 1.0) | Bare `StateGraph(...).compile()` | [examples/langgraph_hello](examples/langgraph_hello) |
| `deepagents` | latest | `create_deep_agent(...)` (a compiled LangGraph) | [examples/deepagents_hello](examples/deepagents_hello) |
| `openai-agents` | 0.17 | `agents.Agent` | [examples/openai_agents_hello](examples/openai_agents_hello) |
| `google-adk` | 1.33 | `google.adk.Agent` | [examples/google_adk_hello](examples/google_adk_hello) |

`langchain`, `langgraph`, `deepagents` all dispatch to the same adapter
(they share the LangChain `Runnable` + `astream_events` substrate). The
three names exist so manifests read honestly.

### Adapter event coverage

|  | LangChain / LangGraph / DeepAgents | OpenAI Agents | Google ADK |
|---|---|---|---|
| `message.delta` (token streaming) | ✓ | ✓ | ✓ |
| `message.completed` (skips empty tool-call turns) | ✓ | ✓ | ✓ |
| `tool.start` / `tool.end` | ✓ | ✓ | ✓ |
| `state.update` | ✓ (graph nodes) | ✓ (agent handoff) | ✓ (multi-agent author) |
| `trace.span` | ✓ (chain spans) |  |  |
| `approval.requested` |  |  |  |
| `cancel(run_id)` (event-boundary) | ✓ | ✓ | ✓ |
| Tool schema → JSON Schema | ✓ | ✓ (native) | ✓ (translated from ADK Schema) |

Gaps are intentional: features get adapter mappings once a consumer needs
them. Adapter code is small enough to extend in a single PR.

---

## Isolation modes

Pick at registry construction time via the `PLATFORM_ISOLATION` env var.

### `in_process` (default)

Agent code is imported into the server process. Lowest overhead. Use when
all agents are trusted and dependency-compatible.

### `subprocess`

Each agent runs in its own `python -m platform_runtime.worker` child
process. The parent never imports agent code. Pipes carry JSON-lines
frames (request envelope, event envelope, error envelope, end marker).

- **Crash containment.** A C-extension segfault, OOM, or runaway
  recursion in one agent kills only its worker; the server and other
  agents keep running.
- **Dependency isolation.** Two agents with incompatible LangChain
  versions can coexist (see below: per-agent venvs).
- **Identical external API.** The HTTP routes and SSE stream are
  byte-for-byte the same as in-process mode.

A `WorkerSupervisor` owns each child: spawns it, demuxes wire frames by
correlation id, drains stderr to the parent's logger, escalates shutdown
(graceful `close` → SIGTERM → SIGKILL). Crashes fail all in-flight
requests with `WorkerCrashed`; restart is explicit (no implicit silent
respawn that hides bugs).

### Per-agent venvs

When a manifest declares `requirements:` and isolation is `subprocess`,
the runtime materializes a per-agent venv at
`~/.cache/platform_runtime/venvs/<agent_id>-<hash>/` and spawns the worker
with that interpreter. The cache key is
`SHA-256(framework + sorted(requirements) + platform_source_path)` —
changing requirements rebuilds; reusing them is instant.

Implementation prefers [`uv`](https://github.com/astral-sh/uv) when
available, falls back to stdlib `venv` + `pip`. Both paths install
`platform-runtime[<framework>]` editable + the agent's requirements.

---

## Configuration

Environment variables consumed by `python -m platform_runtime`:

| Variable | Default | Meaning |
|---|---|---|
| `PLATFORM_AGENTS_DIR` | *(required)* | Directory scanned recursively for `agent.yaml` files. |
| `PLATFORM_ISOLATION` | `in_process` | `in_process` or `subprocess`. |
| `PLATFORM_HOST` | `127.0.0.1` | Bind host. |
| `PLATFORM_PORT` | `8080` | Bind port. |
| `PLATFORM_LOG_LEVEL` | `info` | Standard Python log levels. |

The control plane (when it exists) will manage these declaratively per
deployment. Today they're plain env vars.

---

## Writing a new adapter

Adding framework `X`:

1. **Add the framework to `manifest.SUPPORTED_FRAMEWORKS`** so manifests
   can declare `framework: x`.
2. **Add an `[x]` extras group** to [`pyproject.toml`](pyproject.toml) with
   the SDK's pip dependency.
3. **Add `FRAMEWORK_EXTRAS["x"] = "x"`** in
   [`venv_manager.py`](src/platform_runtime/venv_manager.py) so per-agent
   venvs install the extra.
4. **Create the adapter module** at
   `src/platform_runtime/adapters/<x>_adapter.py`:
   ```python
   from . import register_adapter
   from ..protocol import UnifiedAgentRuntime

   @register_adapter("x")
   class XAdapter(UnifiedAgentRuntime):
       def __init__(self, *, manifest, root, factory): ...
       async def stream(self, request): ...      # yields RuntimeEvent
       async def tools(self): ...                # list[ToolDescriptor]
       async def metadata(self): ...             # AgentMetadata
       # health/aclose have defaults; override if needed
   ```
5. **Activate it** in [`__main__.py`](src/platform_runtime/__main__.py)
   and [`worker.py`](src/platform_runtime/worker.py) under a
   `try / except ImportError` so the extra is genuinely optional.
6. **Ship an example** under `examples/x_hello/` and tests under
   `tests/test_x.py`.

### Invariants `stream()` must honor

The protocol's contract — written in
[`protocol.py`](src/platform_runtime/protocol.py):

- The first yielded event is `RunStarted`.
- The last yielded event is `RunCompleted` *or* `ErrorEvent`.
- `seq` is monotonically increasing per run, starting at 0.
- Every event carries `request.run_id`.
- After the first yield, no exception may escape — all failures become
  `ErrorEvent`.

The existing adapters
([`langchain_adapter.py`](src/platform_runtime/adapters/langchain_adapter.py),
[`openai_agents_adapter.py`](src/platform_runtime/adapters/openai_agents_adapter.py),
[`google_adk_adapter.py`](src/platform_runtime/adapters/google_adk_adapter.py))
follow the same skeleton; copy whichever is closest to your framework's
event model.

---

## Testing

```bash
# Fast suite (default). Covers protocol, manifest, registry, server,
# in-process flow, multi-file imports, all adapter introspection.
python -m pytest tests/ -q -m 'not slow'

# Include subprocess isolation tests (spawn real workers).
python -m pytest tests/ -q

# Include slow tests that build real venvs via pip/uv.
python -m pytest tests/ -q -m 'slow'
```

The full fast suite is 42 tests in ~40s. Subprocess isolation tests add
real `python -m platform_runtime.worker` spawns. The slow venv test
materializes an actual venv with `six` installed (~7s with pip, ~1s with
uv).

Markers:
- `@pytest.mark.subprocess` — spawns real worker processes.
- `@pytest.mark.slow` — materializes a real venv via pip/uv.

---

## Architecture

### Module map

```
src/platform_runtime/
  events.py                  Normalized event schema (Pydantic)
  protocol.py                UnifiedAgentRuntime ABC + request/descriptor models
  manifest.py                AgentManifest + YAML loader + validation
  registry.py                Discovery, isolation-mode dispatch, sys.path setup
  subprocess_supervisor.py   Per-worker pipe owner; demux by correlation id
  ipc.py                     JSON-lines wire protocol shared by parent and child
  worker.py                  python -m platform_runtime.worker <agent_dir>
  venv_manager.py            Per-agent venv build / cache via uv or pip
  server/app.py              FastAPI factory; lifespan owns warmup + shutdown
  adapters/
    __init__.py              @register_adapter decorator + registry
    langchain_adapter.py     LangChain via astream_events(version="v2")
    openai_agents_adapter.py OpenAI Agents via Runner.run_streamed
    google_adk_adapter.py    Google ADK via Runner.run_async
    remote_adapter.py        Subprocess proxy implementing UnifiedAgentRuntime
  __main__.py                Production entrypoint (env-var driven)
```

### Request lifecycle (subprocess mode)

```
HTTP POST /agents/X/stream
   │
   ▼
FastAPI route handler  ─►  registry.get("X").runtime           (RemoteAdapter)
                                       │
                                       ▼
                              supervisor.stream_rpc("stream", InvokeRequest)
                                       │  JSON-lines on stdin
                                       ▼
                              ┌────────────────────────────────┐
                              │ worker process                 │
                              │   reads request frame          │
                              │   adapter.stream(request)      │
                              │   yields RuntimeEvent          │
                              │   each event → JSON-lines on   │
                              │   stdout, tagged with corr-id  │
                              └────────────────────────────────┘
                                       │
   yields events to async generator    ▼
   ◄──────────────────────────  supervisor demuxes by id
   │                              feeds parent's Queue
   ▼
EventSourceResponse  ─►  SSE frames  ─►  client
```

### Why the protocol survives both modes

`UnifiedAgentRuntime` is a thin ABC: five methods, one of them streaming.
The `RemoteAdapter` implements it by proxying over the wire to a worker
that hosts the *real* (in-process) adapter. The same `LangChainAdapter`
serves both isolation modes — in `in_process`, the server holds it
directly; in `subprocess`, the worker holds it and the server holds a
`RemoteAdapter` proxy. The HTTP layer can't tell the difference.

---

## Limitations and roadmap

### Not yet implemented

- **Control plane.** No auth, RBAC, tenants, secret vault, or
  conversation persistence. The runtime trusts its caller.
- **Approval flow.** `approval.requested` is in the schema; no adapter
  emits it yet.
- **Mid-call cancel.** `cancel(run_id)` takes effect at the next event
  boundary inside the adapter's `stream()` — typically within a token
  during a model stream. A run blocked on a single non-streaming model
  or tool call takes longer to release. The wire and HTTP API are
  stable; tightening cancel to mid-call interruption is a future
  refinement.
- **Container isolation.** Docker runner is plumbed for in the design
  (same protocol, different launcher) but not implemented.
- **Reconnect-with-replay.** `Last-Event-ID` is wire-format-ready but
  the server does not persist runs yet.
- **Pause-state persistence.** When the approval flow lands it will
  be in-memory only until the platform backend can persist paused runs
  across restarts.

### Versioning

Event schema and manifest schema are at v1 implicitly. A `manifest_version`
field will arrive the first time a breaking change is needed; the event
schema's discriminated-union design (`type` field) lets us add event
types without breaking existing consumers.

See [TODO.md](../TODO.md) for the full prioritized list.

---

## License

TBD.
