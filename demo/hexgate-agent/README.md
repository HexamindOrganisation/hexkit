# hexgate-agent — a hexgate-wrapped agent on the HexKit contract

A developer backend that serves an agent wrapped with **hexgate** (the
authorization-infrastructure SDK from the security-platform team) over the five
[CONTRACT.md](../CONTRACT.md) endpoints. It exists to demonstrate two things:

1. **Schema compatibility.** Hexgate emits its own normalized event stream;
   HexKit's internal schema is a near-twin. This backend forwards hexgate's
   events verbatim and the proxy's `HexgateTranslator` maps them onto the
   shared `RunEmitter`. The round-trip proves the "same events" decision
   between the two products holds on the wire.
2. **End-to-end user identity.** When the HexKit proxy sends
   `context.user = {id, name, role}` (CONTRACT.md §5), this backend opens an
   `async with hexgate.User(user_id=..., role=...)` block around the run. The
   role drives hexgate's per-tool policy decisions, biscuit attenuation, and
   audit emission to the hexgate cloud — so the demo's HexKit users show up
   in the cloud dashboard tagged with whatever role you set in **Settings**.

## The events

Each event is forwarded as-is, tagged `framework: "hexgate"`:

```
data: {"framework": "hexgate", "event": {"event_type": "block_delta", "block_id": "...", "text": "Hi "}}
```

The proxy's [`HexgateTranslator`](../proxy/src/platform_backend/translators/hexgate.py)
maps these onto the shared `RunEmitter`. Note it is **not** a raw passthrough:
the chat route owns the run envelope (it synthesizes `run_start`/`run_end` and
is the single authority for sequence numbers), so the translator drops
hexgate's own envelope events and re-drives the emitter from the content events
— exactly like the langchain / openai-agents / google-adk translators.

## Prerequisites

- **Python ≥ 3.13** — hexgate requires it (the other demo backends only need
  3.11). The venv below must use a 3.13+ interpreter.
- **`HEXGATE_API_KEY`** (optional, for cloud audit) — the dev/admin key that
  authenticates this backend to your hexgate cloud project. Per-request biscuit
  attenuation scopes each call down to the HexKit user, so one key serves all
  HexKit users.
- **`OPENAI_API_KEY`** — read from this backend's process env. HexKit does not
  send provider keys.

## Run it

```bash
uv venv --python 3.13 demo/hexgate-agent/.venv
uv pip install --python demo/hexgate-agent/.venv -e 'demo/hexgate-agent[dev]'

# Optional: stream policy decisions to the hexgate cloud dashboard.
export HEXGATE_API_KEY=...

demo/hexgate-agent/.venv/bin/python -m hexgate_agent     # serves on :8080
```

The agent registers as `guard` with `framework: "hexgate"`. Sending it a
"what time is it?" message exercises the tool-call path: the call comes
through as hexgate `tool_start`/`tool_end` and lands in the **tool-calls**
widget in HexKit's chat surface.

## Verify the contract

The proxy's smoke check works against any contract-conformant backend:

```bash
demo/hexgate-agent/.venv/bin/python demo/scripts/verify_backend.py http://127.0.0.1:8080
```

## User identity and policy

[`run_hexgate_agent`](src/hexgate_agent/agent.py) reads `context.user.id` and
`context.user.role` and opens `async with hexgate.User(...)` around
`stream_agent(...)`. From there, hexgate's policy enforcement picks the role's
rules from your `policy.yaml` (or your registered cloud policy) and audit events
stream to the cloud, tagged with the HexKit user. **Policy enforcement** is
opt-in — add `agent = agent.enforce_policy("policy.yaml")` after
`create_agent(...)` once you want denials to flow through too; a blocked tool
surfaces as a hexgate `error` event, which the translator already handles.
