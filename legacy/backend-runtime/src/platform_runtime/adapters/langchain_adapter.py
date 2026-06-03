"""
LangChain adapter.

Wraps any LangChain `Runnable` (LCEL chain, agent executor, chat model, ...)
and translates its `astream_events(version="v2")` output into the platform's
normalized `RuntimeEvent` stream.

Why `astream_events` and not callback handlers?
-----------------------------------------------
`astream_events` is LangChain's own normalization layer: it produces a single
event stream regardless of whether the wrapped object is an LLM, a chain, or
an agent. Translating *its* event names is a small finite mapping. Writing a
`BaseCallbackHandler` would force us to reassemble the same logic ourselves
and miss LCEL composition events.

The factory contract
--------------------
The registry hands us a `factory` (the callable named in the manifest under
`agent_callable`). On first use we call `factory()`. The result must be a
LangChain `Runnable`. If `factory()` returns a coroutine, we await it.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Callable
from uuid import uuid4

# LangChain is an optional extra. Importing this module asserts it is
# installed; the core package does not import this module directly.
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from ..events import StreamEvent
from ..run_emitter import RunEmitter, extract_query
from ..manifest import AgentManifest
from ..protocol import (
    AgentMetadata,
    HealthStatus,
    InvokeRequest,
    ToolDescriptor,
    UnifiedAgentRuntime,
)
from . import register_adapter
from .credentials_cache import CredentialsCache


@register_adapter("langchain", "langgraph", "deepagents")
class LangChainAdapter(UnifiedAgentRuntime):
    """Adapter for LangChain `Runnable` objects."""

    def __init__(
        self,
        *,
        manifest: AgentManifest,
        root: Path,
        factory: Callable[..., Any],
    ) -> None:
        self._manifest = manifest
        self._root = root
        self._factory = factory

        def _validate(result: Any) -> None:
            if not isinstance(result, Runnable):
                raise TypeError(
                    f"Factory '{self._manifest.agent_callable}' returned "
                    f"{type(result).__name__}, expected a LangChain Runnable."
                )

        # Per-credentials runnable cache. When `request.context.credentials` is
        # set AND the factory accepts a `credentials` kwarg, the cache builds
        # one runnable per credential-hash. Otherwise it collapses to a single
        # cached entry — identical to the pre-credentials behavior.
        self._runnables = CredentialsCache(factory, validator=_validate)
        # run_id → cancel signal. Populated when `stream()` begins, popped
        # in its `finally`. `cancel()` sets the matching event.
        self._cancel_signals: dict[str, asyncio.Event] = {}

    # ------------------------------------------------------------------
    # Lazy runnable construction
    # ------------------------------------------------------------------

    async def _get_runnable(self, context: dict[str, Any] | None = None) -> Runnable:
        """Get (and lazily build) the runnable for this request's credentials.

        Pass `request.context` from `stream()` so per-user credentials route
        to a credential-specific runnable. `tools()` and `health()` pass
        nothing — they introspect or probe with no user context.
        """
        return await self._runnables.get(context or {})

    # ------------------------------------------------------------------
    # Streaming: the core method
    # ------------------------------------------------------------------

    async def stream(
        self, request: InvokeRequest
    ) -> AsyncIterator[StreamEvent]:
        run_id = request.run_id
        emitter = RunEmitter(run_id, agent_id=self._manifest.agent_id)
        cancel_signal = asyncio.Event()
        self._cancel_signals[run_id] = cancel_signal

        # First event: RunStartEvent. From this point on, no exception may
        # escape this generator — we convert them to ErrorEvent.
        for ev in emitter.run_start(
            query=extract_query(request.input),
            input=_safe_input_for_event(request.input),
        ):
            yield ev

        try:
            runnable = await self._get_runnable(request.context)
        except Exception as e:
            self._cancel_signals.pop(run_id, None)
            for ev in emitter.error(
                f"Failed to build LangChain runnable: {e}", recoverable=False
            ):
                yield ev
            return

        # Map an lc tool-run id → our tool_id (minted per call so the wire
        # stream is self-consistent across adapters).
        tool_ids: dict[str, str] = {}
        # Track open chain spans for trace emission. We record the start
        # time so the matching on_chain_end can produce a completed span.
        open_spans: dict[str, _OpenSpan] = {}

        final_output: Any = None

        translated_input = translate_input(request.input)

        try:
            async for lc_event in runnable.astream_events(
                translated_input,
                version="v2",
                config={"run_id": run_id, "metadata": request.context},
            ):
                if cancel_signal.is_set():
                    for ev in emitter.error(
                        "Run cancelled",
                        recoverable=False,
                        details={"cancelled": True},
                    ):
                        yield ev
                    return
                name = lc_event.get("event")
                lc_run_id = lc_event.get("run_id", "")
                data = lc_event.get("data") or {}

                if name == "on_chat_model_stream" or name == "on_llm_stream":
                    # Streamed token → text block keyed by the model run id.
                    # The block opens lazily on the first non-empty delta.
                    chunk = data.get("chunk")
                    for ev in emitter.text_delta(
                        lc_run_id, _extract_text(chunk)
                    ):
                        yield ev

                elif name == "on_chat_model_end" or name == "on_llm_end":
                    # Close the streamed block. If the model never streamed
                    # (non-streaming client) but produced text, emit it as a
                    # complete block. A tool-call turn has no text → nothing
                    # is emitted, and tool activity surfaces via tool events.
                    if emitter.has_block(lc_run_id):
                        for ev in emitter.end_block(lc_run_id):
                            yield ev
                    else:
                        text = _extract_text(data.get("output"))
                        for ev in emitter.full_text_block(text):
                            yield ev

                elif name == "on_tool_start":
                    tool_id = uuid4().hex
                    tool_ids[lc_run_id] = tool_id
                    for ev in emitter.tool_start(
                        tool_id=tool_id,
                        tool_name=lc_event.get("name", "tool"),
                        arguments=_coerce_dict(data.get("input")),
                    ):
                        yield ev

                elif name == "on_tool_end":
                    tool_id = tool_ids.pop(lc_run_id, uuid4().hex)
                    for ev in emitter.tool_end(
                        tool_id=tool_id,
                        tool_name=lc_event.get("name", "tool"),
                        output=_jsonable(data.get("output")),
                    ):
                        yield ev

                elif name == "on_chain_start":
                    # Open a span for every chain that starts. We do not
                    # emit anything yet — the matching on_chain_end will
                    # produce a single completed TraceSpanEvent.
                    open_spans[lc_run_id] = _OpenSpan(
                        name=lc_event.get("name", "chain"),
                        start_ts=_utcnow(),
                        parent_ids=tuple(lc_event.get("parent_ids") or ()),
                    )

                elif name == "on_chain_end":
                    parent_ids = lc_event.get("parent_ids") or []

                    if not parent_ids:
                        # Root run terminal output. Used to populate
                        # RunEndEvent.output. Robust across LangChain shapes
                        # (LCEL RunnableSequence, LangGraph CompiledStateGraph,
                        # custom Runnable wrapper).
                        final_output = _jsonable(data.get("output"))

                    else:
                        # state_update: emit only for DIRECT children of the
                        # root run. For LangGraph these are the graph nodes
                        # ("model", "tools", ...), and their outputs are the
                        # state increment. Filtering by depth keeps the
                        # event stream signal-rich — LCEL noise inside a
                        # node is not surfaced as state.
                        if (
                            len(parent_ids) == 1
                            and parent_ids[0] == run_id
                        ):
                            output = data.get("output")
                            if output not in (None, {}, [], ""):
                                for ev in emitter.state_update(
                                    lc_event.get("name", "node"),
                                    _jsonable(output),
                                ):
                                    yield ev

                    # Close the span and emit a TraceSpanEvent for any
                    # non-root chain. The root is omitted: it is already
                    # represented by run_start / run_end.
                    span = open_spans.pop(lc_run_id, None)
                    if span is not None and parent_ids:
                        for ev in emitter.trace_span(
                            span_id=lc_run_id,
                            parent_span_id=parent_ids[0] if parent_ids else None,
                            name=span.name,
                            start_ts=span.start_ts,
                            end_ts=_utcnow(),
                            attributes={"lc_event": "chain"},
                        ):
                            yield ev

                # Every other LangChain event is intentionally dropped at
                # this stage (on_retriever_*, on_prompt_*, ...). They can
                # be promoted to spans/state when a concrete UI need arises.

        except Exception as e:
            for ev in emitter.error(
                f"LangChain stream failed: {e}",
                recoverable=False,
                details={"exception_type": type(e).__name__},
            ):
                yield ev
            return
        finally:
            self._cancel_signals.pop(run_id, None)

        for ev in emitter.run_end(output=final_output):
            yield ev

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    async def tools(self) -> list[ToolDescriptor]:
        """Best-effort tool list.

        LangChain has no universal `runnable.tools` attribute; tool exposure
        depends on the runnable shape. We probe the common cases (agent
        executors, tool-bound models). Unknown shapes → empty list.
        """
        runnable = await self._get_runnable()
        candidates: list[BaseTool] = []

        # Legacy AgentExecutor.tools
        attr = getattr(runnable, "tools", None)
        if isinstance(attr, list):
            candidates.extend(t for t in attr if isinstance(t, BaseTool))

        # ChatModel.bind_tools(...) result keeps tools in .kwargs
        kwargs = getattr(runnable, "kwargs", None)
        if isinstance(kwargs, dict):
            bound = kwargs.get("tools") or []
            for t in bound:
                if isinstance(t, BaseTool):
                    candidates.append(t)

        # LangGraph CompiledStateGraph (the shape `create_agent` returns).
        # Walk its nodes looking for a langgraph ToolNode; each node is a
        # PregelNode whose actual implementation is in `.bound`. We duck-type
        # on `tools_by_name` to avoid importing langgraph in the core path.
        nodes = getattr(runnable, "nodes", None)
        if isinstance(nodes, dict):
            for pregel_node in nodes.values():
                impl = getattr(pregel_node, "bound", pregel_node)
                tools_by_name = getattr(impl, "tools_by_name", None)
                if isinstance(tools_by_name, dict):
                    for t in tools_by_name.values():
                        if isinstance(t, BaseTool):
                            candidates.append(t)

        descriptors: list[ToolDescriptor] = []
        seen: set[str] = set()
        for tool in candidates:
            if tool.name in seen:
                continue
            seen.add(tool.name)
            descriptors.append(
                ToolDescriptor(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=_tool_input_schema(tool),
                )
            )
        return descriptors

    async def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_id=self._manifest.agent_id,
            name=self._manifest.name,
            framework=self._manifest.framework,
            version=self._manifest.version,
            description=self._manifest.description,
            capabilities=self._manifest.capabilities,
            actions=list(self._manifest.actions),
            extra=self._manifest.extra,
        )

    async def health(self) -> HealthStatus:
        # We do NOT call the model here; that would be a remote round-trip
        # on every healthcheck. Just verify the runnable is constructable.
        try:
            await self._get_runnable()
            return HealthStatus(ok=True)
        except Exception as e:
            return HealthStatus(ok=False, details={"error": str(e)})

    async def cancel(self, run_id: str) -> bool:
        signal = self._cancel_signals.get(run_id)
        if signal is None or signal.is_set():
            return False
        signal.set()
        return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _OpenSpan:
    """Bookkeeping for a chain span between on_chain_start and on_chain_end."""

    __slots__ = ("name", "start_ts", "parent_ids")

    def __init__(self, name: str, start_ts: datetime, parent_ids: tuple) -> None:
        self.name = name
        self.start_ts = start_ts
        self.parent_ids = parent_ids


def _extract_text(obj: Any) -> str:
    """Pull printable text out of a LangChain chunk / message / dict."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    # AIMessageChunk / AIMessage / BaseMessage subclasses
    content = getattr(obj, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Multimodal: list of dicts with {"type": "text", "text": "..."}
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
        return "".join(parts)
    if isinstance(obj, dict):
        if isinstance(obj.get("content"), str):
            return obj["content"]
    return ""


def _coerce_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    return {"value": _jsonable(value)}


def _jsonable(value: Any) -> Any:
    """Best-effort conversion to JSON-serializable shape for event payloads."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    # LangChain messages and similar pydantic objects
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:
            pass
    return repr(value)


def _safe_input_for_event(value: Any) -> dict[str, Any]:
    coerced = _jsonable(value)
    if isinstance(coerced, dict):
        return coerced
    return {"value": coerced}


def _tool_input_schema(tool: BaseTool) -> dict[str, Any]:
    schema_cls = getattr(tool, "args_schema", None)
    if schema_cls is None:
        return {}
    try:
        return schema_cls.model_json_schema()
    except Exception:
        return {}

def translate_input(input: dict[str, list[dict[str, str]]]) -> dict[str, list[Any]]:
    res = {"messages": []}
    for message in input.get("messages", []):
        role = message.get("role")
        content = message.get("content", "")
        if role == "user":
            res["messages"].append(HumanMessage(content=content))
        elif role == "assistant":
            res["messages"].append(AIMessage(content=content))
        elif role == "system":
            res["messages"].append(SystemMessage(content=content))
    return res