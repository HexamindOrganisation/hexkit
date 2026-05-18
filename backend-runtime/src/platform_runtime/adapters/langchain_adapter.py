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
import inspect
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Callable
from uuid import uuid4

# LangChain is an optional extra. Importing this module asserts it is
# installed; the core package does not import this module directly.
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from ..events import (
    ErrorEvent,
    MessageCompleted,
    MessageDelta,
    RunCompleted,
    RunStarted,
    RuntimeEvent,
    StateUpdate,
    ToolEnd,
    ToolStart,
    TraceSpan,
)
from ..manifest import AgentManifest
from ..protocol import (
    AgentMetadata,
    HealthStatus,
    InvokeRequest,
    ToolDescriptor,
    UnifiedAgentRuntime,
)
from . import register_adapter


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
        self._runnable: Runnable | None = None
        self._lock = asyncio.Lock()  # guards lazy factory() call
        # run_id → cancel signal. Populated when `stream()` begins, popped
        # in its `finally`. `cancel()` sets the matching event.
        self._cancel_signals: dict[str, asyncio.Event] = {}

    # ------------------------------------------------------------------
    # Lazy runnable construction
    # ------------------------------------------------------------------

    async def _get_runnable(self) -> Runnable:
        """Call the factory once, then cache the resulting Runnable.

        The factory may be sync or async. We accept both because agent
        authors writing LCEL chains tend to write sync factories, while
        authors using async-only model clients write async ones.
        """
        if self._runnable is not None:
            return self._runnable

        async with self._lock:
            if self._runnable is not None:
                return self._runnable
            result = self._factory()
            if inspect.isawaitable(result):
                result = await result
            if not isinstance(result, Runnable):
                raise TypeError(
                    f"Factory '{self._manifest.agent_callable}' returned "
                    f"{type(result).__name__}, expected a LangChain Runnable."
                )
            self._runnable = result
            return result

    # ------------------------------------------------------------------
    # Streaming: the core method
    # ------------------------------------------------------------------

    async def stream(
        self, request: InvokeRequest
    ) -> AsyncIterator[RuntimeEvent]:
        run_id = request.run_id
        seq = _SeqCounter()
        cancel_signal = asyncio.Event()
        self._cancel_signals[run_id] = cancel_signal

        # First event: RunStarted. From this point on, no exception may
        # escape this generator — we convert them to ErrorEvent.
        yield RunStarted(
            run_id=run_id,
            seq=seq.next(),
            agent_id=self._manifest.agent_id,
            input=_safe_input_for_event(request.input),
        )

        try:
            runnable = await self._get_runnable()
        except Exception as e:
            self._cancel_signals.pop(run_id, None)
            yield ErrorEvent(
                run_id=run_id,
                seq=seq.next(),
                message=f"Failed to build LangChain runnable: {e}",
                recoverable=False,
            )
            return

        # Track open tool calls so on_tool_end can resolve back to ids.
        tool_calls: dict[str, str] = {}  # lc_run_id -> our tool_call_id
        # Track open assistant messages by lc model-run-id.
        message_ids: dict[str, str] = {}
        # Track open chain spans for trace emission. We record the start
        # time so the matching on_chain_end can produce a completed span.
        open_spans: dict[str, _OpenSpan] = {}

        final_output: Any = None

        try:
            async for lc_event in runnable.astream_events(
                request.input,
                version="v2",
                config={"run_id": run_id, "metadata": request.context},
            ):
                if cancel_signal.is_set():
                    yield ErrorEvent(
                        run_id=run_id,
                        seq=seq.next(),
                        message="Run cancelled",
                        recoverable=False,
                        details={"cancelled": True},
                    )
                    return
                name = lc_event.get("event")
                lc_run_id = lc_event.get("run_id", "")
                data = lc_event.get("data") or {}

                if name == "on_chat_model_start" or name == "on_llm_start":
                    message_ids[lc_run_id] = uuid4().hex

                elif name == "on_chat_model_stream" or name == "on_llm_stream":
                    chunk = data.get("chunk")
                    delta = _extract_text(chunk)
                    if not delta:
                        continue
                    msg_id = message_ids.setdefault(lc_run_id, uuid4().hex)
                    yield MessageDelta(
                        run_id=run_id,
                        seq=seq.next(),
                        message_id=msg_id,
                        delta=delta,
                    )

                elif name == "on_chat_model_end" or name == "on_llm_end":
                    output = data.get("output")
                    text = _extract_text(output)
                    msg_id = message_ids.pop(lc_run_id, uuid4().hex)
                    yield MessageCompleted(
                        run_id=run_id,
                        seq=seq.next(),
                        message_id=msg_id,
                        role="assistant",
                        content=text or "",
                        metadata={"lc_run_id": lc_run_id},
                    )

                elif name == "on_tool_start":
                    tool_call_id = uuid4().hex
                    tool_calls[lc_run_id] = tool_call_id
                    yield ToolStart(
                        run_id=run_id,
                        seq=seq.next(),
                        tool_call_id=tool_call_id,
                        name=lc_event.get("name", "tool"),
                        arguments=_coerce_dict(data.get("input")),
                    )

                elif name == "on_tool_end":
                    tool_call_id = tool_calls.pop(lc_run_id, uuid4().hex)
                    yield ToolEnd(
                        run_id=run_id,
                        seq=seq.next(),
                        tool_call_id=tool_call_id,
                        name=lc_event.get("name", "tool"),
                        output=_jsonable(data.get("output")),
                    )

                elif name == "on_chain_start":
                    # Open a span for every chain that starts. We do not
                    # emit anything yet — the matching on_chain_end will
                    # produce a single completed TraceSpan.
                    open_spans[lc_run_id] = _OpenSpan(
                        name=lc_event.get("name", "chain"),
                        start_ts=_utcnow(),
                        parent_ids=tuple(lc_event.get("parent_ids") or ()),
                    )

                elif name == "on_chain_end":
                    parent_ids = lc_event.get("parent_ids") or []

                    if not parent_ids:
                        # Root run terminal output. Used to populate
                        # RunCompleted.output. Robust across LangChain shapes
                        # (LCEL RunnableSequence, LangGraph CompiledStateGraph,
                        # custom Runnable wrapper).
                        final_output = _jsonable(data.get("output"))

                    else:
                        # State.update: emit only for DIRECT children of the
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
                                yield StateUpdate(
                                    run_id=run_id,
                                    seq=seq.next(),
                                    key=lc_event.get("name", "node"),
                                    value=_jsonable(output),
                                )

                    # Close the span and emit TraceSpan for any non-root
                    # chain. The root is omitted: it is already represented
                    # by run.started / run.completed.
                    span = open_spans.pop(lc_run_id, None)
                    if span is not None and parent_ids:
                        yield TraceSpan(
                            run_id=run_id,
                            seq=seq.next(),
                            span_id=lc_run_id,
                            parent_span_id=parent_ids[0] if parent_ids else None,
                            name=span.name,
                            start_ts=span.start_ts,
                            end_ts=_utcnow(),
                            attributes={"lc_event": "chain"},
                        )

                # Every other LangChain event is intentionally dropped at
                # this stage (on_retriever_*, on_prompt_*, ...). They can
                # be promoted to spans/state when a concrete UI need arises.

        except Exception as e:
            yield ErrorEvent(
                run_id=run_id,
                seq=seq.next(),
                message=f"LangChain stream failed: {e}",
                recoverable=False,
                details={"exception_type": type(e).__name__},
            )
            return
        finally:
            self._cancel_signals.pop(run_id, None)

        yield RunCompleted(
            run_id=run_id,
            seq=seq.next(),
            agent_id=self._manifest.agent_id,
            output=final_output,
        )

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

class _SeqCounter:
    __slots__ = ("_n",)

    def __init__(self) -> None:
        self._n = -1

    def next(self) -> int:
        self._n += 1
        return self._n


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
