# HexaUI Developer Contract (v1)

> The contract between a **developer's agent backend** and the **HexaUI proxy**.
> It imposes only the **shape of the API** (five endpoints) and that each stream
> frame is **tagged with the framework that produced it**. You do *not* rewrite
> your agent's events: you forward your framework's **native** events, tagged,
> and the **proxy translates** them into the one unified schema the UI consumes.
>
> The reference implementation in [`agent-server/`](agent-server/) demonstrates
> every supported framework; the proxy-side translators live in
> [`proxy/.../translators/`](proxy/src/platform_backend/translators/).

---

## 1. Roles

```
browser ──HTTP/SSE──▶ HexaUI proxy ──HTTP/SSE──▶ your agent backend
                       (this platform)            (you implement this)
```

- Your **backend** runs the agent and **forwards its native events** over the
  stream, each tagged with the `framework` that produced it. Your server layer
  is thin: iterate your agent's existing event stream, JSON-project each event,
  emit it. You change **no agent code**.
- The **proxy** owns auth, persistence, secret encryption, auto-titling, **and
  translation**: it selects the translator for your `framework` and normalizes
  your native events into the single rich internal schema the frontend renders.

---

## 2. Endpoints (the imposed API shape)

All paths are relative to your backend's base URL
(`PLATFORM_AGENT_BACKEND_URL`, default `http://127.0.0.1:8080`).

| Method + path | Purpose |
|---|---|
| `GET /agents` | roster: `[{id, name, role, main_color, ui_url}]` |
| `GET /agents/{id}/ui` | per-agent `ui.yaml` (`text/yaml`) with `page.main_color` + widgets |
| `POST /agents/{id}/stream` | SSE run — framework-tagged native events (§5) |
| `POST /agents/{id}/cancel` | body `{run_id}` → `{cancelled: bool}` |
| `POST /agents/{id}/actions/{name}` | optional widget action → `{result, events}` |

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
    "credentials": { "openai_api_key": "sk-...", "anthropic_api_key": "..." },
    "files": [ { "id": "uuid", "name": "notes.txt", "mime": "text/plain", "size": 123, "content": "…" } ]
  }
}
```

- `run_id` — opaque id the proxy assigns; accept it on `cancel`.
- `input.messages` — the chat transcript.
- `context.credentials` — the user's decrypted secrets, flat `{provider}_api_key`.
  **Use them only for the run; never persist or log them.**
- `context.files` — files the user attached to the conversation (persist across
  turns; forwarded every run). `content` is the decoded text for text mimes,
  `null` for binary (fetch by `id` is post-v1). Inline them into the prompt /
  provider content blocks as your framework needs.

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

---

## 6. Supported frameworks

`framework` selects a proxy-side translator. Forward the JSON projection of that
framework's native streaming events:

| `framework` | Native stream you forward | Reference |
|---|---|---|
| `langchain` / `langgraph` / `deepagents` | `runnable.astream_events(version="v2")` events | [`translators/langchain.py`](proxy/src/platform_backend/translators/langchain.py) |
| `openai-agents` | `Runner.run_streamed(...).stream_events()` items | [`translators/openai_agents.py`](proxy/src/platform_backend/translators/openai_agents.py) |
| `google-adk` | `Runner.run_async(...)` `Event`s | [`translators/google_adk.py`](proxy/src/platform_backend/translators/google_adk.py) |
| `native` | **the escape hatch** — already-normalized minimal events (below) | [`translators/native.py`](proxy/src/platform_backend/translators/native.py) |

Native event shapes each translator understands (the JSON projection — the
reference [`agents/demos.py`](agent-server/src/agent_server/agents/demos.py)
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
- persists user + assistant messages (with `run_id`), bumps `updated_at`,
  auto-titles new conversations.

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
- [ ] Credentials from `context.credentials` are used per-run and never persisted.

The reference [`agent-server/`](agent-server/) passes all of the above for every
supported framework; see [`scripts/`](scripts/) for the executable checks.

---

## 3. `GET /agents` — roster  ·  ## 4. `GET /agents/{id}/ui` — per-agent UI

Unchanged. Roster entry: `{id, name, role, main_color, ui_url}` — `main_color`
is the single accent color (hex) for the active agent; `ui_url` points to the
agent's `ui.yaml`. `ui.yaml` is `text/yaml` with `page.main_color` + a `widgets`
list (types from the `custom-UI` library, e.g. `ai-response`, `ai-chat-input`,
`tool-calls`); `404` falls back to a default chat layout. Conversation history
and the file tree are shell chrome, not widgets.
