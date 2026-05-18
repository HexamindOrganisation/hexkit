"""
Google ADK (Agent Development Kit) adapter.

Wraps any `google.adk.Agent` and translates the SDK's `Runner.run_async(...)`
event stream into the platform's normalized `RuntimeEvent` stream.

How ADK exposes a run
---------------------
ADK is session-oriented: you construct a `Runner` (agent + app_name +
session_service), then call `runner.run_async(user_id=..., session_id=...,
new_message=Content(...))` which is an async generator yielding `Event`s.

Each Event carries:
  - `content`: a `google.genai.types.Content` whose `parts` may be text,
    function_call, or function_response.
  - `partial`: True for incremental chunks (token deltas), False/None on
    finalized turn content.
  - `turn_complete`: True on the final event of a turn.
  - `author`: which agent in a multi-agent app produced this event.

Mapping highlights
------------------
  text part, partial=True             →  MessageDelta
  text part, not partial              →  MessageCompleted
  function_call part                  →  ToolStart
  function_response part              →  ToolEnd
  event.author change (multi-agent)   →  StateUpdate(key="active_agent")
"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any, AsyncIterator, Callable
from uuid import uuid4

# ADK is an optional extra. Importing this module asserts it is installed;
# the core package does not import this module directly.
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types as genai_types

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


@register_adapter("google-adk")
class GoogleADKAdapter(UnifiedAgentRuntime):
    """Adapter for Google ADK `Agent` objects."""

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
        self._runner: Runner | None = None
        self._session_service: InMemorySessionService | None = None
        self._lock = asyncio.Lock()
        self._cancel_signals: dict[str, asyncio.Event] = {}

    # ------------------------------------------------------------------
    # Lazy agent / runner construction
    # ------------------------------------------------------------------

    async def _get_runner(self) -> Runner:
        """Build the agent + runner on first use, cache for the rest.

        We build the runner here (not in the factory) because the platform
        owns operational concerns: session storage, app naming, etc. The
        agent author writes a `build_agent()` that returns an `Agent`; the
        adapter wraps it with a runner.
        """
        if self._runner is not None:
            return self._runner

        async with self._lock:
            if self._runner is not None:
                return self._runner

            result = self._factory()
            if inspect.isawaitable(result):
                result = await result
            if not isinstance(result, Agent):
                raise TypeError(
                    f"Factory '{self._manifest.agent_callable}' returned "
                    f"{type(result).__name__}, expected google.adk.Agent."
                )

            self._agent = result
            # In-memory sessions keep us from depending on external storage
            # for the first iteration. Multi-host deployments will inject
            # a real SessionService via a future constructor argument.
            self._session_service = InMemorySessionService()
            self._runner = Runner(
                app_name=self._manifest.agent_id,
                agent=self._agent,
                session_service=self._session_service,
                auto_create_session=True,
            )
            return self._runner

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

        yield RunStarted(
            run_id=run_id,
            seq=seq.next(),
            agent_id=self._manifest.agent_id,
            input=_safe_input_for_event(request.input),
        )

        try:
            runner = await self._get_runner()
        except Exception as e:
            self._cancel_signals.pop(run_id, None)
            yield ErrorEvent(
                run_id=run_id,
                seq=seq.next(),
                message=f"Failed to build ADK runner: {e}",
                recoverable=False,
            )
            return

        # Convert the platform's free-form input into an ADK Content.
        try:
            new_message = _to_content(request.input)
        except Exception as e:
            self._cancel_signals.pop(run_id, None)
            yield ErrorEvent(
                run_id=run_id,
                seq=seq.next(),
                message=f"Could not convert input to Content: {e}",
                recoverable=False,
            )
            return

        # Identifiers ADK needs. We use the platform run_id as the session
        # id so each run is isolated; user_id is pulled from the request
        # context (control-plane caller may populate it), defaulting to
        # "anonymous". A future multi-turn API will reuse session_id.
        user_id = str(request.context.get("user_id") or "anonymous")
        session_id = run_id

        # Per-run id maps. function_call.id ↔ our tool_call_id.
        tool_call_ids: dict[str, str] = {}
        current_message_id: str | None = None
        current_message_author: str | None = None
        last_author: str | None = None
        last_text: str = ""

        try:
            async for ev in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=new_message,
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

                # Multi-agent transitions surface as StateUpdate so the UI
                # can render "now talking to: X". `author` is the agent
                # that produced this event.
                author = getattr(ev, "author", None)
                if author and author != last_author:
                    last_author = author
                    yield StateUpdate(
                        run_id=run_id,
                        seq=seq.next(),
                        key="active_agent",
                        value=author,
                    )

                content = getattr(ev, "content", None)
                parts = getattr(content, "parts", None) or []
                partial = bool(getattr(ev, "partial", False))

                for part in parts:
                    text = getattr(part, "text", None)
                    func_call = getattr(part, "function_call", None)
                    func_resp = getattr(part, "function_response", None)

                    if text:
                        if partial:
                            # Start a new message on the first delta we see
                            # for this author. The author switch above means
                            # a new agent starts a new message id.
                            if (
                                current_message_id is None
                                or current_message_author != author
                            ):
                                current_message_id = uuid4().hex
                                current_message_author = author
                                last_text = ""
                            yield MessageDelta(
                                run_id=run_id,
                                seq=seq.next(),
                                message_id=current_message_id,
                                delta=text,
                            )
                            last_text += text
                        else:
                            # Fully-formed text in one event. Use the
                            # pending message id if we have one (we were
                            # streaming deltas), else mint a new one.
                            msg_id = current_message_id or uuid4().hex
                            current_message_id = None
                            current_message_author = None
                            last_text = text
                            yield MessageCompleted(
                                run_id=run_id,
                                seq=seq.next(),
                                message_id=msg_id,
                                role="assistant",
                                content=text,
                                metadata={"author": author or ""},
                            )

                    elif func_call is not None:
                        call_id = getattr(func_call, "id", None) or uuid4().hex
                        tool_call_id = uuid4().hex
                        tool_call_ids[call_id] = tool_call_id
                        yield ToolStart(
                            run_id=run_id,
                            seq=seq.next(),
                            tool_call_id=tool_call_id,
                            name=getattr(func_call, "name", "tool"),
                            arguments=_coerce_args(
                                getattr(func_call, "args", None)
                            ),
                        )

                    elif func_resp is not None:
                        call_id = getattr(func_resp, "id", "") or ""
                        tool_call_id = tool_call_ids.pop(call_id, uuid4().hex)
                        yield ToolEnd(
                            run_id=run_id,
                            seq=seq.next(),
                            tool_call_id=tool_call_id,
                            name=getattr(func_resp, "name", "tool"),
                            output=_jsonable(
                                getattr(func_resp, "response", None)
                            ),
                        )

                # If this event finalized the turn and we had a pending
                # streamed message, emit its MessageCompleted now using the
                # accumulated text. Without this, callers would never see
                # a terminal message frame for streamed responses.
                if getattr(ev, "turn_complete", False) and current_message_id is not None:
                    yield MessageCompleted(
                        run_id=run_id,
                        seq=seq.next(),
                        message_id=current_message_id,
                        role="assistant",
                        content=last_text,
                        metadata={"author": current_message_author or ""},
                    )
                    current_message_id = None
                    current_message_author = None
                    last_text = ""

        except Exception as e:
            yield ErrorEvent(
                run_id=run_id,
                seq=seq.next(),
                message=f"Google ADK stream failed: {e}",
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
            output={"text": last_text} if last_text else None,
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    async def tools(self) -> list[ToolDescriptor]:
        runner = await self._get_runner()
        agent: Agent = runner.agent  # type: ignore[assignment]
        descriptors: list[ToolDescriptor] = []

        for tool in getattr(agent, "tools", None) or []:
            name = getattr(tool, "name", None)
            if not name:
                continue
            description = getattr(tool, "description", "") or ""
            schema: dict[str, Any] = {}

            # FunctionTool exposes `_get_declaration()` returning a
            # `FunctionDeclaration` whose `parameters` is a `Schema`. We
            # try to convert it to a plain JSON-Schema dict so the platform
            # contract stays uniform across adapters.
            if isinstance(tool, FunctionTool):
                try:
                    decl = tool._get_declaration()
                    schema = _schema_to_json_schema(
                        getattr(decl, "parameters", None)
                    )
                except Exception:
                    schema = {}

            descriptors.append(
                ToolDescriptor(
                    name=name,
                    description=description,
                    input_schema=schema,
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
            await self._get_runner()
            return HealthStatus(ok=True)
        except Exception as e:
            return HealthStatus(ok=False, details={"error": str(e)})

    async def cancel(self, run_id: str) -> bool:
        signal = self._cancel_signals.get(run_id)
        if signal is None or signal.is_set():
            return False
        signal.set()
        return True

    async def aclose(self) -> None:
        runner = self._runner
        if runner is not None:
            try:
                close = getattr(runner, "close", None)
                if close is not None:
                    result = close()
                    if inspect.isawaitable(result):
                        await result
            except Exception:
                pass
        self._runner = None
        self._agent = None
        self._session_service = None


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


def _to_content(value: Any) -> genai_types.Content:
    """Convert the platform's free-form `input` into an ADK Content.

    Accepts:
        - `str`                                  → wrapped as one text part
        - dict with `input` / `content` / `text` → unwrap and wrap as above
        - a `genai_types.Content`                → passed through
        - anything else                          → `repr()` as text
    """
    if isinstance(value, genai_types.Content):
        return value
    if isinstance(value, str):
        text = value
    elif isinstance(value, dict):
        for key in ("input", "content", "text"):
            v = value.get(key)
            if isinstance(v, str):
                text = v
                break
        else:
            text = repr(value)
    else:
        text = repr(value)
    return genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=text)],
    )


def _coerce_args(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    return {"value": _jsonable(value)}


def _jsonable(value: Any) -> Any:
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


def _safe_input_for_event(value: Any) -> dict[str, Any]:
    coerced = _jsonable(value)
    if isinstance(coerced, dict):
        return coerced
    return {"value": coerced}


# ---------------------------------------------------------------------------
# ADK Schema → JSON Schema conversion
# ---------------------------------------------------------------------------

_TYPE_MAP = {
    "STRING": "string",
    "NUMBER": "number",
    "INTEGER": "integer",
    "BOOLEAN": "boolean",
    "ARRAY": "array",
    "OBJECT": "object",
}


def _schema_to_json_schema(schema: Any) -> dict[str, Any]:
    """Translate ADK's `Schema` (google.genai.types) into JSON Schema.

    ADK schemas mirror OpenAPI / JSON Schema closely but use a `Type` enum
    for primitive types and have `properties` / `items` as nested Schemas.
    We walk recursively and emit the equivalent JSON-Schema dict.
    """
    if schema is None:
        return {}

    out: dict[str, Any] = {}
    t = getattr(schema, "type", None)
    if t is not None:
        # Could be a Type enum or a string.
        t_str = getattr(t, "value", None) or str(t)
        out["type"] = _TYPE_MAP.get(t_str, t_str.lower())

    description = getattr(schema, "description", None)
    if description:
        out["description"] = description

    enum = getattr(schema, "enum", None)
    if enum:
        out["enum"] = list(enum)

    properties = getattr(schema, "properties", None)
    if isinstance(properties, dict):
        out["properties"] = {
            name: _schema_to_json_schema(child)
            for name, child in properties.items()
        }

    required = getattr(schema, "required", None)
    if required:
        out["required"] = list(required)

    items = getattr(schema, "items", None)
    if items is not None:
        out["items"] = _schema_to_json_schema(items)

    return out
