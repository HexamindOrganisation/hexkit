# hexa-gate-agent — a fortify-wrapped agent on the HexaUI contract

A developer backend that serves an agent wrapped with **fortify** (a sibling
team's agent-runtime security SDK) over the five [CONTRACT.md](../CONTRACT.md)
endpoints. It exists to test one thing: **fortify and HexaUI agreed to share an
event schema — does that actually hold on the wire?**

## The idea

Fortify wraps a framework runtime and emits its *own* normalized event stream
via `fortify.stream_agent(...)`. That schema is a near-twin of HexaUI's internal
`hexa-events` schema — both descend from the same unified-runtime vocabulary
(same `event_type` names, `block_type`, `ToolCallState`, and `run_id`/`sequence`
envelope).

So this backend does **not** reshape fortify's events into the minimal `native`
vocabulary. It forwards them **verbatim**, tagged `framework: "fortify"`:

```
data: {"framework": "fortify", "event": {"event_type": "block_delta", "block_id": "...", "text": "Hi "}}
```

and the proxy's new [`FortifyTranslator`](../proxy/src/platform_backend/translators/fortify.py)
maps them onto the shared `RunEmitter`. Note it is **not** a raw passthrough:
the proxy's chat route owns the run envelope (it synthesizes `run_start`/`run_end`
and is the single authority for sequence numbers), so the translator drops
fortify's own envelope events and re-drives the emitter from the content events —
exactly like the langchain / openai-agents / google-adk translators.

> **Why a translator, not `native` passthrough?** The `native` framework reads a
> different, minimal `{"type": "text"}` vocabulary, and the proxy has no
> raw-passthrough path (every frame goes through one emitter that owns
> sequencing). Tagging fortify's rich events as `native` would render nothing.
> A `fortify` translator is the idiomatic fit and the genuine test of schema
> unity. See the design discussion in the PR/commit for the full rationale.

## Prerequisites

- **Python ≥ 3.13** — fortify requires it (the other demo backends only need
  3.11). The venv below must use a 3.13+ interpreter.
- **The fortify SDK cloned outside this repo.** It's unpublished, so clone the
  source and reference it as an editable path dependency (already wired in
  [pyproject.toml](pyproject.toml)):

  ```bash
  git clone https://github.com/HexamindOrganisation/coolagents.git \
    ~/Documents/hexa-gate-sdk     # sibling of custom_UI; never inside it
  ```

## Run it

From the repo root, under WSL (the venv is Linux), same pattern as the other
backends:

```bash
uv venv --python 3.13 demo/hexa-gate-agent/.venv
uv pip install --python demo/hexa-gate-agent/.venv -e 'demo/hexa-gate-agent[dev]'
AGENT_HOST=127.0.0.1 AGENT_PORT=8080 \
  demo/hexa-gate-agent/.venv/bin/python -m hexa_gate_agent     # serves on :8080
```

Point the proxy at it (`PLATFORM_RUNTIME_URL=http://127.0.0.1:8080`, its
default), run the front-app, pick **Fortify Guard**, and chat. Try
"what time is it?" to exercise the tool path — the `get_server_time` call flows
through as fortify `tool_start`/`tool_end` and lands in the **tool-calls**
widget.

The agent reads the OpenAI key from `context.credentials.openai_api_key`
(forwarded per-run by the proxy) — add it in the UI, or set `OPENAI_API_KEY` for
a standalone run. Model defaults to `gpt-4o-mini`; override with `FORTIFY_MODEL`.

## Verify it conforms

With the backend running, in another shell:

```bash
demo/hexa-gate-agent/.venv/bin/python demo/scripts/verify_backend.py http://127.0.0.1:8080
```

The checker acts as the proxy would — assigns a `run_id`, reads the SSE stream,
cancels mid-run, validates every frame's shape — and prints PASS/FAIL per
[CONTRACT.md §8](../CONTRACT.md).

## What's wrapped (and what isn't)

`create_agent(...)` returns a `FortifyAgent` — the runtime wrap whose normalized
event stream this backend tests. **Policy enforcement** (fortify's other half:
permissions/policies on tools) is intentionally left out to keep the demo
runnable without a policy bundle / OPA. To add it, apply a policy to the agent
in [agent.py](src/hexa_gate_agent/agent.py):

```python
agent = agent.enforce_policy("policy.yaml")   # see the SDK's examples/
```

A denied tool then surfaces as a fortify `error` event — which the translator
already handles, so it flows to the UI with no further changes.
