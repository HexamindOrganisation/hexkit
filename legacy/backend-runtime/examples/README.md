# Examples

Each subdirectory is one wrapped agent: an `agent.yaml` manifest plus the
entrypoint module it points to. The platform discovers them all when given
this folder as `PLATFORM_AGENTS_DIR`.

## langchain_hello

A LangChain tool-calling agent with one tool (`get_current_time`).

### Install

```bash
# from backend-runtime/
pip install -e .[langchain]
pip install langchain-openai  # provider-specific, not bundled
```

### Run

```bash
export OPENAI_API_KEY=...
export PLATFORM_AGENTS_DIR=examples
python -m platform_runtime
```

Server starts on `http://127.0.0.1:8080`.

### Try it

List agents:

```bash
curl http://127.0.0.1:8080/agents
```

Get metadata / tools / health:

```bash
curl http://127.0.0.1:8080/agents/langchain-hello/metadata
curl http://127.0.0.1:8080/agents/langchain-hello/tools
curl http://127.0.0.1:8080/agents/langchain-hello/health
```

Non-streaming invoke (returns the terminal `RunEndEvent`):

```bash
curl -X POST http://127.0.0.1:8080/agents/langchain-hello/invoke \
  -H "Content-Type: application/json" \
  -d '{"input": {"messages": [{"role": "user", "content": "What time is it in Paris?"}]}}'
```

Streaming run (SSE — frames are `event: <type>\nid: <id>\ndata: <json>`):

```bash
curl -N -X POST http://127.0.0.1:8080/agents/langchain-hello/stream \
  -H "Content-Type: application/json" \
  -d '{"input": {"messages": [{"role": "user", "content": "What time is it in Paris?"}]}}'
```

You should see a sequence like:

```
event: run_start
event: block_start         (the model's reasoning/decision text opens)
event: block_delta         (× many — token stream)
event: block_end
event: tool_start          (tool_name: get_current_time)
event: tool_end
event: block_start         (the final answer opens)
event: block_delta         (× many)
event: block_end
event: run_end
```
