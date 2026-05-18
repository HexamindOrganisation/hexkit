"""
OpenAI Agents SDK adapter.

Wraps any `agents.Agent` instance and translates the SDK's
`Runner.run_streamed(...).stream_events()` output into the platform's
normalized `RuntimeEvent` stream.

Why `Runner.run_streamed`
-------------------------
The SDK exposes three high-level entry points: `run`, `run_sync`,
`run_streamed`. Only the streamed one emits incremental events. It returns
a `RunResultStreaming` synchronously; calling `.stream_events()` on it
gives the async iterator we map.

The factory contract
--------------------
The registry hands us a `factory` (named in the manifest under
`agent_callable`). On first use we call `factory()`. The result must be an
`agents.Agent`. If `factory()` returns a coroutine, we await it.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Callable
from uuid import uuid4

# OpenAI Agents SDK is an optional extra. Importing this module asserts it
# is installed; the core package does not import this module directly.
from agents import (
    Agent,
    AgentUpdatedStreamEvent,
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    Runner,
)

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


@register_adapter("openai-agents")
class OpenAIAgentsAdapter(UnifiedAgentRuntime):
    """Adapter for OpenAI Agents SDK `Agent` objects."""

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
        self._agent: Agent | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lazy agent construction
    # ------------------------------------------------------------------

    async def _get_agent(self) -> Agent:
        if self._agent is not None:
            return self._agent
        async with self._lock:
            if self._agent is not None:
                return self._agent
            result = self._factory()
            if inspect.isawaitable(result):
                result = await result
            if not isinstance(result, Agent):
                raise TypeError(
                    f"Factory '{self._manifest.agent_callable}' returned "
                    f"{type(result).__name__}, expected agents.Agent."
                )
            self._agent = result
            return result

    # ------------------------------------------------------------------
    # Streaming: the core method
    # ------------------------------------------------------------------

    async def stream(
        self, request: InvokeRequest
    ) -> AsyncIterator[RuntimeEvent]:
        run_id = request.run_id
        seq = _SeqCounter()

        # First event: RunStarted. Past this point no exception may escape;
        # everything becomes an ErrorEvent.
        yield RunStarted(
            run_id=run_id,
            seq=seq.next(),
            agent_id=self._manifest.agent_id,
            input=_safe_input_for_event(request.input),
        )

        try:
            agent = await self._get_agent()
        except Exception as e:
            yield ErrorEvent(
                run_id=run_id,
                seq=seq.next(),
                message=f"Failed to build agent: {e}",
                recoverable=False,
            )
            return

        # Map an SDK tool-call's `call_id` (assigned by OpenAI's Responses
        # API) to our own platform-level tool_call_id. We mint our own so
        # the wire stream is self-consistent across adapters.
        tool_call_ids: dict[str, str] = {}
        # The model can stream multiple distinct messages within one run
        # (e.g. think → tool-call → final reply). Each gets its own id.
        current_message_id: str | None = None

        result = None
        try:
            result = Runner.run_streamed(agent, request.input)
            async for ev in result.stream_events():

                if isinstance(ev, RawResponsesStreamEvent):
                    # Raw OpenAI Responses API stream events. We only
                    # forward textual token deltas as MessageDelta; the
                    # rest of the raw stream (response.created, .completed,
                    # function-call.* arguments deltas, ...) is implicit
                    # in the higher-level RunItem events.
                    data = ev.data
                    data_type = getattr(data, "type", None)

                    if data_type == "response.output_text.delta":
                        delta_text = getattr(data, "delta", "") or ""
                        if not delta_text:
                            continue
                        if current_message_id is None:
                            current_message_id = uuid4().hex
                        yield MessageDelta(
                            run_id=run_id,
                            seq=seq.next(),
                            message_id=current_message_id,
                            delta=delta_text,
                        )

                elif isinstance(ev, RunItemStreamEvent):
                    name = ev.name
                    item = ev.item

                    if name == "message_output_created":
                        # A fully-formed assistant message just landed.
                        text = _extract_message_text(item)
                        msg_id = current_message_id or uuid4().hex
                        current_message_id = None  # next deltas start a new message
                        yield MessageCompleted(
                            run_id=run_id,
                            seq=seq.next(),
                            message_id=msg_id,
                            role="assistant",
                            content=text,
                            metadata={
                                "sdk_item_type": getattr(item, "type", ""),
                            },
                        )

                    elif name == "tool_called":
                        raw = getattr(item, "raw_item", None)
                        call_id = getattr(raw, "call_id", None) or uuid4().hex
                        tool_call_id = uuid4().hex
                        tool_call_ids[call_id] = tool_call_id
                        yield ToolStart(
                            run_id=run_id,
                            seq=seq.next(),
                            tool_call_id=tool_call_id,
                            name=getattr(raw, "name", "tool"),
                            arguments=_safe_json_args(
                                getattr(raw, "arguments", None)
                            ),
                        )

                    elif name == "tool_output":
                        raw = getattr(item, "raw_item", None)
                        call_id = _coerce_call_id(raw)
                        tool_call_id = tool_call_ids.pop(
                            call_id, uuid4().hex
                        )
                        yield ToolEnd(
                            run_id=run_id,
                            seq=seq.next(),
                            tool_call_id=tool_call_id,
                            name=_resolve_tool_name(raw, item),
                            output=_jsonable(getattr(item, "output", None)),
                        )

                    # `handoff_requested`, `handoff_occured`,
                    # `mcp_*`, `reasoning_item_created`, `tool_search_*`
                    # are intentionally dropped at this stage. We can map
                    # them as the UI grows widgets for them.

                elif isinstance(ev, AgentUpdatedStreamEvent):
                    # A handoff just changed the active agent. Surface as
                    # state.update so the UI can show "now talking to: X".
                    yield StateUpdate(
                        run_id=run_id,
                        seq=seq.next(),
                        key="active_agent",
                        value=getattr(ev.new_agent, "name", ""),
                    )

        except Exception as e:
            yield ErrorEvent(
                run_id=run_id,
                seq=seq.next(),
                message=f"OpenAI Agents stream failed: {e}",
                recoverable=False,
                details={"exception_type": type(e).__name__},
            )
            return

        final_output: Any = None
        if result is not None:
            final_output = _jsonable(getattr(result, "final_output", None))

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
        agent = await self._get_agent()
        descriptors: list[ToolDescriptor] = []
        for tool in getattr(agent, "tools", None) or []:
            name = getattr(tool, "name", None)
            if not name:
                continue
            descriptors.append(
                ToolDescriptor(
                    name=name,
                    description=getattr(tool, "description", "") or "",
                    input_schema=getattr(tool, "params_json_schema", None) or {},
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
        try:
            await self._get_agent()
            return HealthStatus(ok=True)
        except Exception as e:
            return HealthStatus(ok=False, details={"error": str(e)})


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


def _safe_input_for_event(value: Any) -> dict[str, Any]:
    coerced = _jsonable(value)
    if isinstance(coerced, dict):
        return coerced
    return {"value": coerced}


def _jsonable(value: Any) -> Any:
    """Best-effort conversion to JSON-serializable shape for event payloads."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:
            pass
    return repr(value)


def _safe_json_args(value: Any) -> dict[str, Any]:
    """Coerce a tool-call arguments payload into a dict.

    The SDK stores arguments as a JSON-encoded string on the raw tool call.
    We try to parse it; on failure return it raw under a 'value' key so the
    information is preserved.
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        import json
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"value": value}
    return {"value": _jsonable(value)}


def _coerce_call_id(raw: Any) -> str:
    """Pull `call_id` from a raw tool-output item.

    Output items can be either a Pydantic model or a plain dict depending
    on SDK version. Try attribute access, then key access, then fall back
    to an empty string (the caller mints a uuid when this returns falsy).
    """
    if raw is None:
        return ""
    if hasattr(raw, "call_id"):
        return getattr(raw, "call_id", "") or ""
    if isinstance(raw, dict):
        return str(raw.get("call_id", ""))
    return ""


def _resolve_tool_name(raw: Any, item: Any) -> str:
    """Best-effort tool name extraction for a tool_output event."""
    if raw is not None:
        if hasattr(raw, "name"):
            n = getattr(raw, "name", None)
            if n:
                return str(n)
        if isinstance(raw, dict) and raw.get("name"):
            return str(raw["name"])
    return getattr(item, "type", "tool") or "tool"


def _extract_message_text(item: Any) -> str:
    """Pull printable text from a MessageOutputItem.

    The raw item is a `ResponseOutputMessage` whose `content` is a list of
    output content parts. We flatten the `output_text` parts into a string.
    """
    raw = getattr(item, "raw_item", None)
    if raw is None:
        return ""
    content = getattr(raw, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            text = getattr(part, "text", None)
            if isinstance(text, str):
                parts.append(text)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "".join(parts)
    return ""
