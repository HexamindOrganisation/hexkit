# HexKit Developer Contract (v1)

> The contract between a **developer's agent backend** and the **HexKit proxy**.
> It imposes only the **shape of the API** (five endpoints) and that each stream
> frame is **tagged with the framework that produced it**. You do *not* rewrite
> your agent's events: you forward your framework's **native** events, tagged,
> and the **proxy translates** them into the one unified schema the UI consumes.
>
> The reference implementation in [`agent-server/`](demo/agent-server/) demonstrates
> every supported framework; the proxy-side translators live in
> [`proxy-server/.../translators/`](proxy-server/src/platform_backend/translators/).

---

## 1. Roles

```
browser ──HTTP/SSE──▶ HexKit proxy ──HTTP/SSE──▶ your agent backend
                       (this platform)            (you implement this)
```

- Your **backend** runs the agent and **forwards its native events** over the
  stream, each tagged with the `framework` that produced it. Your server layer
  is thin: iterate your agent's existing event stream, JSON-project each event,
  emit it. You change **no agent code**.
- The **proxy** owns auth, persistence, auto-titling, **and translation**: it
  selects the translator for your `framework` and normalizes your native events
  into the single rich internal schema the frontend renders.

---

## 2. Endpoints (the imposed API shape)

All paths are relative to your backend's base URL
(`PLATFORM_AGENT_BACKEND_URL`, default `http://127.0.0.1:8880`).

| Method + path | Purpose |
|---|---|
| `GET /agents` | roster: `[{id, name, role, main_color, ui_url}]` |
| `GET /agents/{id}/ui` | per-agent `ui.yaml` (`text/yaml`) with `page.main_color` + widgets |
| `POST /agents/{id}/stream` | SSE run — framework-tagged native events (§5) |
| `POST /agents/{id}/cancel` | body `{run_id}` → `{cancelled: bool}` |
| `POST /agents/{id}/forget` | body `{conversation_id}` → `{forgotten: bool}` — erase that conversation's memory (§5) |
| `POST /agents/{id}/actions/{name}` | widget action / data source → `{result}` (§5b) |

Unknown `{id}` → `404`. (§3/§4 — roster and `ui.yaml` — are unchanged from the
previous revision; see those sections at the end.)

---

## 5. `POST /agents/{id}/stream` — the run

### Request body (proxy → your backend)

```json
{
  "run_id": "hex32",
  "input": { "messages": [ { "role": "user", "content": "..." } ] },
  "context": {
    "conversation_id": "uuid",
    "files": [ { "id": "uuid", "name": "notes.txt", "mime": "text/plain", "size": 123, "content": "…" } ],
    "user": { "id": "uuid", "name": "Alice Anderson", "role": "billing" }
  }
}
```

- `run_id` — opaque id the proxy assigns; accept it on `cancel`.
- `input.messages` — the chat transcript.
- **Provider API keys are *not* in the context.** HexKit does not store or forward
  them — your backend reads its own provider keys (OpenAI, Google, …) from its
  own environment. The platform never holds your model credentials.
- `context.files` — files the user attached to the conversation (persist across
  turns; forwarded every run). `content` is the decoded text for text mimes,
  `null` for binary (fetch by `id` is post-v1). Inline them into the prompt /
  provider content blocks as your framework needs.
- `context.user` — caller identity. Always exactly three keys: `id` (the HexKit
  user uuid), `name` (display name or `null`), and `role` (free-text string or
  `null`). HexKit does not interpret `role`; it's there so policy-aware runtimes
  (hexgate, etc.) can scope per-call decisions to the calling user.
  **NEVER** includes email, password hash, or any internal identifier. An agent
  backend that doesn't use this can ignore the block.

### Conversation memory (the backend owns it)

HexUI does **not** manage conversation memory. Each `stream` carries only the
new user turn; the proxy never sends prior messages. **Your backend owns the
conversation context, keyed by `(context.user.id, context.conversation_id)`** —
you decide what prior turns to feed the model (full history, a window, a
summary, retrieval, …). Rules:

- **Cold ids start fresh.** Accept a `conversation_id` you've never seen and
  begin a new conversation — never error on an unknown id.
- **Per `(user, agent, conversation)`.** A `conversation_id` never spans two
  agents; switching agents starts a new thread.
- **You own durability.** If you keep memory in-process only, multi-turn context
  is lost on restart (HexUI still shows the past transcript it stored for
  display, but your model won't have it). Persist if that matters to you.
- **`files` / context items are not memory** — they arrive in full each turn
  (above); treat them as the current attachments.

> HexUI still stores the user-visible transcript for its own sidebar / reload —
> but that display log is never sent to you and is not your memory.

### Response — framework-tagged native events

`Content-Type: text/event-stream`. Each event is one SSE frame whose `data:` is:

```
data: {"framework": "<name>", "event": <your framework's native event, JSON-projected>}
```

- `framework` — which translator the proxy applies (see §6). Constant for a run.
- `event` — your framework's native event, made JSON-serializable. You forward
  it as-is; you don't reshape it into our schema.

You do **NOT** emit `run_start`, `run_end`, run ids, sequence numbers, block
lifecycle, or any envelope — the proxy synthesizes all of that. End the stream
(EOF) when the run is done; `{"event": {"type": "done"}}` is also accepted.

### Cancellation

The proxy may call `POST /agents/{id}/cancel` with `{"run_id": "..."}` while a
stream is open. Stop producing events and end the stream — the proxy finalizes
and persists the partial text. Return `{cancelled: true}` if the run was found,
`false` otherwise.

### Forget (memory lifecycle)

When the user deletes a conversation, the proxy calls
`POST /agents/{id}/forget` with `{"conversation_id": "..."}`. Erase that
conversation's memory and return `{forgotten: true}` (or `false` if you had
nothing for it). Idempotent — forgetting an unknown id is still `200`. This is
the only way the user's "delete conversation" can reach the memory you own, so
implement it for any backend that stores conversation state (covers
"clear history" and right-to-erasure).

---

## 5b. Widget behavior — actions & data sources

Beyond the chat turn, a `ui.yaml` can wire interactive widgets. The model is
deliberately small: **one privileged behavior the platform owns (the chat turn),
plus exactly two dev-facing primitives — `action` (do) and `data_source`
(display).** Widgets never run dev code in the browser; every behavior is a call
to one of *your* actions.

### `POST /agents/{id}/actions/{name}` — the one behavior endpoint

Request: `{"args": { ... }}` — the widget's payload (form values, button args, or
a data-source's args). Response: **`{"result": <json>}`**. That's it — an action
returns a single result; it does **not** push to the UI. (Unknown `{name}` →
`404`; the proxy passes your status + body through verbatim.)

This one endpoint backs both primitives:

- **`action` (do)** — a button click or form submit calls the named action for
  its side effect. The `result` is available to the calling widget (e.g. a
  form's success state); nothing else happens automatically.
- **`data_source` (display)** — a display widget (table, form prefill, …) calls
  the named action to *fetch* what it shows. `args` come from the widget's
  `data_source.args`. Return the data as the `result`.

### How widgets update — pull, never push

There is **no server push to widgets** and nothing widget-related on the chat
stream. When an action changes data another widget shows, that widget simply
**re-pulls its `data_source`**. The YAML wires this declaratively with a
`refresh` list naming the widgets to re-pull after an action succeeds:

```yaml
widgets:
  - { type: table, name: findings, data_source: { action: list_findings } }
  - type: button-group
    name: ops
    buttons:
      - { label: "Re-run scan", action: run_scan, refresh: [findings] }
  - type: form
    name: add
    fields: [ ... ]
    submit_action: add_finding
    refresh: [findings]          # re-pull `findings` after a successful submit
```

Your backend stays **UI-agnostic** — it only implements actions
(`run_scan`, `add_finding`, `list_findings`) and never references widget names.
`refresh` (the one place widget names appear) lives in the YAML, which is the
sole wiring layer. The proxy turns `refresh` into re-pulls of those widgets'
`data_source` actions — i.e. more calls to this same endpoint.

> Tool calls shown in a `tool-calls` widget are **not** actions — they're part of
> the chat turn's event stream (§5), pushed by the platform during a run. Actions
> and data sources are the only dev-configured widget behaviors.

---

## 6. Supported frameworks

`framework` selects a proxy-side translator. Forward the JSON projection of that
framework's native streaming events:

| `framework` | Native stream you forward | Reference |
|---|---|---|
| `langchain` / `langgraph` / `deepagents` | `runnable.astream_events(version="v2")` events | [`translators/langchain.py`](proxy-server/src/platform_backend/translators/langchain.py) |
| `openai-agents` | `Runner.run_streamed(...).stream_events()` items | [`translators/openai_agents.py`](proxy-server/src/platform_backend/translators/openai_agents.py) |
| `google-adk` | `Runner.run_async(...)` `Event`s | [`translators/google_adk.py`](proxy-server/src/platform_backend/translators/google_adk.py) |
| `native` | **the escape hatch** — already-normalized minimal events (below) | [`translators/native.py`](proxy-server/src/platform_backend/translators/native.py) |

Native event shapes each translator understands (the JSON projection — the
reference [`agents/demos.py`](demo/agent-server/src/agent_server/agents/demos.py)
emits exactly these):

```
# langchain (astream_events v2)
{"event":"on_chat_model_stream","run_id":"m1","data":{"chunk":{"content":"Hi "}}}
{"event":"on_chat_model_end","run_id":"m1","data":{}}
{"event":"on_tool_start","run_id":"t1","name":"search","data":{"input":{"q":"x"}}}
{"event":"on_tool_end","run_id":"t1","name":"search","data":{"output":{...}}}

# openai-agents (stream_events)
{"type":"raw_response","data":{"type":"response.output_text.delta","delta":"Hi "}}
{"type":"run_item","name":"message_output_created","item":{"raw_item":{"content":[{"text":"..."}]}}}
{"type":"run_item","name":"tool_called","item":{"raw_item":{"call_id":"c1","name":"search","arguments":"{\"q\":\"x\"}"}}}
{"type":"run_item","name":"tool_output","item":{"raw_item":{"call_id":"c1","name":"search"},"output":{...}}}

# google-adk (Event)
{"author":"assistant","partial":true,"content":{"parts":[{"text":"Hi "}]}}
{"author":"assistant","content":{"parts":[{"function_call":{"id":"c1","name":"search","args":{"q":"x"}}}]}}
{"author":"assistant","content":{"parts":[{"function_response":{"id":"c1","name":"search","response":{...}}}]}}

# native (escape hatch)
{"type":"text","text":"..."}            {"type":"reasoning","text":"..."}
{"type":"tool","id":"t1","name":"search","args":{...},"widget":"tool-calls"}
{"type":"tool_result","id":"t1","output":{...}|"error":"..."}
{"type":"error","message":"..."}        {"type":"done"}
```

**Serializing native events.** Framework events aren't always plain JSON (e.g.
LangChain chunks are `AIMessageChunk` objects). Your server layer JSON-projects
them — a `model_dump()` / attribute-scrape per event. The shapes above are what
the translators read; a forward helper that produces them is all your server
layer needs. New framework → add a translator in the proxy (the dev side doesn't
change); a framework we don't support → use `native`.

---

## 7. What the proxy does (you don't have to)

For each run the proxy:

- emits `run_start` before your first event;
- routes each `{framework, event}` frame to that framework's translator, which
  maps native events onto a `RunEmitter` — opening/closing text & reasoning
  blocks, turning tool calls into `tool_start`/`tool_end` with the rich envelope
  (run ids, sequence numbers, the `widget` field, default `tool-calls`);
- emits `run_end` at end-of-stream, accumulating the final assistant message;
- frames every synthesized event in the internal hexa SSE schema and pipes it to
  the browser, where the frontend bridge maps it to UI widget events;
- persists user + assistant messages (with `run_id`) **as the display transcript
  only**, bumps `updated_at`, auto-titles new conversations.

What the proxy does **not** do: it does not manage conversation memory. It sends
you only the new turn and calls `/forget` when a conversation is deleted — the
model context is yours to own (see "Conversation memory" in §5).

The rich internal schema is the proxy-internal [`hexa-events`](packages/hexa-events/)
package; developers never see or depend on it.

---

## 8. Conformance checklist

- [ ] `GET /agents` returns entries with `id`, `name`, `role`, `main_color`, `ui_url`.
- [ ] `GET /agents/{id}/ui` returns `text/yaml` with `page.main_color` + widgets; `404` when absent.
- [ ] `POST /agents/{id}/stream` accepts the §5 body and returns `text/event-stream`.
- [ ] Each stream frame is `data: {"framework": "...", "event": <native event>}`.
- [ ] `framework` is one of the supported values (or `native`).
- [ ] `POST /agents/{id}/cancel` with `{run_id}` stops the run and returns `{cancelled: bool}`.
- [ ] `POST /agents/{id}/actions/{name}` accepts `{args}` and returns `{result}` (only if the agent's `ui.yaml` uses `action` / `data_source`).
- [ ] The backend owns conversation memory keyed by `conversation_id`, accepts unseen ids, and treats `input.messages` as the new turn only.
- [ ] `POST /agents/{id}/forget` with `{conversation_id}` erases that conversation's memory and returns `{forgotten: bool}`.
- [ ] Provider API keys are read from the backend's own environment — never expected in the request.

The reference [`agent-server/`](demo/agent-server/) passes all of the above for every
supported framework; see [`scripts/`](demo/scripts/) for the executable checks.

**Check your own backend.** Run [`scripts/verify_backend.py`](demo/scripts/verify_backend.py)
against any running backend URL — it acts as the proxy would (assigns a `run_id`,
reads the SSE stream, cancels mid-run, validates every frame's shape) and prints
PASS/FAIL per item above, exiting non-zero on failure:

```bash
python scripts/verify_backend.py http://127.0.0.1:8880 [--agent <id>]
```

**Start from a template.** [`starter-agent/`](demo/starter-agent/) is the smallest
conformant backend — the whole contract in one annotated file. Copy it and fill
in the three `# CHANGE ME` spots.

---

## 3. `GET /agents` — roster  ·  ## 4. `GET /agents/{id}/ui` — per-agent UI

Unchanged. Roster entry: `{id, name, role, main_color, ui_url}` — `main_color`
is the single accent color (hex) for the active agent; `ui_url` points to the
agent's `ui.yaml`. `ui.yaml` is `text/yaml` with `page.main_color` + a `widgets`
list (types from the `custom-UI` library, e.g. `ai-response`, `ai-chat-input`,
`tool-calls`); `404` falls back to a default chat layout. Conversation history
and the file tree are shell chrome, not widgets.
