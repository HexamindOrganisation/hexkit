# LLM example backend

FastAPI backend for the agent-ui [`llm` example](..). Provides an
OpenAI-backed streaming chat endpoint and an in-memory conversation store.

## Run

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
uvicorn main:app --reload --port 8000
```

Then in another terminal, from the repo root:

```bash
npm run example:llm
```

## Endpoints

- `GET  /conversations` — list of conversation summaries (matches the
  `list_conversations` action)
- `POST /conversations` — create a new empty conversation; returns the
  summary (matches the `create_conversation` action wired to
  `ai-history`'s `+ New chat` button)
- `GET  /conversations/{id}` — messages for one conversation (matches
  `load_conversation`)
- `POST /chat` — streams an OpenAI completion as plain text. Body:
  `{ "messages": [...], "conversation_id": "..." }`. When
  `conversation_id` is provided, the user message and final assistant
  reply are appended to that conversation, and its title/preview are
  updated from the first user message. Each call is timed and its
  token usage folded into the running totals exposed at `/metrics`.
- `GET  /metrics` — cumulative LLM metrics for this server process
  (matches the `get_metrics` action). Returns `{ requests, total_tokens,
  cost, latency }` in the shape the agent-ui `metrics` widget expects
  (primitives or `{ value, delta?, hint? }`). Cost is a rough estimate
  derived from a small per-1M-token pricing table keyed by
  `OPENAI_MODEL`.

## Notes

The store and metrics are in-memory only — restarting the server resets
everything.
