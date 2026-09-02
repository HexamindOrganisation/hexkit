"""
The chat endpoint.

`POST /conversations/{id}/messages` is the centerpiece of the platform:

1. Persist the incoming user message.
2. Assemble the conversation history into the backend's `{"messages": [...]}`
   input shape.
3. Open the developer backend's MINIMAL SSE stream and NORMALIZE it into the
   rich internal event schema (`DevStreamTranslator` owns a `RunEmitter` that
   synthesizes run ids, sequence numbers, block lifecycle, and the
   `run_start` / `run_end` envelope), frame each event with `to_sse_frame`, and
   pipe it to the browser. Persist the assistant's final text + `run_id` from
   the translator's accumulated result.
4. Auto-title the conversation on the first user message.
5. Track the active `run_id` in-memory so `POST /conversations/{id}/cancel`
   can target it.

Notes:
- The developer backend speaks only the minimal contract (see CONTRACT.md); the
  rich hexa schema is an internal proxy↔frontend detail produced here.
- Disconnect during the stream: FastAPI's `request.is_disconnected()` flips, we
  finalize + persist the partial accumulated text, and the upstream stream is
  closed by httpx when our generator exits.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from hexa_events import RunEmitter, extract_query, to_sse_frame
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import runtime_client
from ..auth.deps import current_user
from ..db import get_session, session_factory
from ..models.conversation import Conversation
from ..models.message import Message
from ..models.user import User
from ..schemas.chat import ActionIn, CancelOut, ChatMessageIn
from ..sse import iter_frames
from ..translators import get_translator
from .conversations import (
    conversation_context_items,
    conversation_files,
    link_files,
)

router = APIRouter(prefix="/conversations", tags=["chat"])
logger = logging.getLogger("platform_backend.chat")


def _decode_text(content: bytes, mime: str) -> str | None:
    """Return decoded text for a file, or None for binary.

    Don't trust the mime alone — browsers often upload text files as
    `application/octet-stream`. We treat any bytes that decode cleanly as UTF-8
    as text (covers .txt/.md/.json/.csv/etc. regardless of mime); a declared
    text/* mime uses lossy decode so it's never dropped.
    """
    if mime.startswith("text/"):
        return content.decode("utf-8", "replace")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _files_payload(files: list) -> list[dict]:
    """Shape a conversation's files for `context.files`; decode text content."""
    return [
        {
            "id": str(f.id),
            "name": f.name,
            "mime": f.mime,
            "size": f.size,
            "content": _decode_text(f.content, f.mime),
        }
        for f in files
    ]


# Conversation-id → active run_id. In-memory: a process-restart loses the
# mapping, which matches the runtime's own model (cancel is process-lifetime,
# see legacy/backend-runtime/README.md). Durable cancel is post-v0.
_active_runs: dict[uuid.UUID, str] = {}

# run_ids the user explicitly cancelled. The cancel route adds the id; the chat
# stream reads it to (a) stop pulling and (b) roll the turn back so a cancelled
# prompt + partial reply never feed the next run. Disconnect detection alone is
# unreliable, and an agent that stops on cancel just EOFs like a normal finish.
_cancelled_runs: set[str] = set()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _owned_conversation(
    session: AsyncSession, user_id: uuid.UUID, conv_id: uuid.UUID
) -> Conversation:
    conv = await session.get(Conversation, conv_id)
    if conv is None or conv.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found"
        )
    return conv


def _autotitle(text: str) -> str:
    """Heuristic title from the first user message: first non-blank line,
    trimmed to 60 chars with an ellipsis on overflow. The point is a
    sidebar-friendly label, not a precis."""
    line = text.strip().splitlines()[0] if text.strip() else ""
    if len(line) <= 60:
        return line
    return line[:57].rstrip() + "…"


# ---------------------------------------------------------------------------
# Chat (streaming)
# ---------------------------------------------------------------------------

@router.post("/{conv_id}/messages")
async def post_message(
    conv_id: uuid.UUID,
    body: ChatMessageIn,
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    conv = await _owned_conversation(session, user.id, conv_id)

    # Persist the user message and (if this is the first one) the auto-title
    # in the same commit, so a crash before the upstream call leaves a clean
    # row pair rather than a titled-but-empty conversation.
    is_first_message = (
        await session.execute(
            select(Message.id)
            .where(Message.conversation_id == conv_id)
            .limit(1)
        )
    ).first() is None
    user_message = Message(
        conversation_id=conv.id, role="user", content=body.content
    )
    session.add(user_message)
    if is_first_message and not conv.title:
        conv.title = _autotitle(body.content)
    await session.commit()
    await session.refresh(user_message)
    await session.refresh(conv)

    # The proxy forwards ONLY the new user turn — the agent owns conversation
    # memory, keyed by `context.conversation_id` (CONTRACT §5). The user +
    # assistant rows we persist are the *display* transcript (sidebar / reload),
    # never the model context.
    turn = [{"role": "user", "content": body.content}]

    # Link any newly-attached files to the conversation, then forward ALL of the
    # conversation's files (attachments persist across turns).
    if body.file_ids:
        await link_files(session, conv.id, user.id, body.file_ids)
        await session.commit()
    files_payload = _files_payload(await conversation_files(session, conv.id))
    # Widget content toggled into context (table / markdown) rides the same
    # `context.files` channel — the agent inlines it identically; the `name`
    # (the widget's label) tells the model what it is.
    for item in await conversation_context_items(session, conv.id):
        files_payload.append(
            {
                "id": f"ctx:{item.key}",
                "name": item.label,
                "mime": item.mime,
                "size": len(item.content.encode("utf-8")),
                "content": item.content,
            }
        )
    # Ground truth for "the LLM ignores my file": shows what we actually
    # forward. `content=None` means the bytes weren't valid UTF-8 (PDF / image /
    # docx / xlsx …) so the agent inlines "[binary file omitted]" and the model
    # has nothing to read — extract text upstream or send provider file blocks.
    if files_payload:
        logger.info(
            "forwarding %d file(s) to agent %r: %s",
            len(files_payload),
            conv.agent_id,
            [
                {
                    "name": f["name"],
                    "mime": f["mime"],
                    "size": f["size"],
                    "content_chars": len(f["content"]) if f["content"] else None,
                }
                for f in files_payload
            ],
        )
    else:
        logger.info("no files attached to conversation %s for this run", conv.id)

    run_id = uuid.uuid4().hex
    agent_id = conv.agent_id

    runtime_body = {
        "input": {"messages": turn},
        "run_id": run_id,
        "context": {
            "conversation_id": str(conv.id),
            "files": files_payload,
            # Caller identity. `role` is an opaque string the developer's
            # agent can interpret however they like (e.g. opening an
            # `async with hexgate.User(role=...)` block for policy
            # enforcement). NEVER includes email, password hash, or any
            # internal ids beyond the user uuid.
            "user": {
                "id": str(user.id),
                "name": user.name,
                "role": user.role,
            },
        },
    }

    input_payload = {"messages": turn}
    emitter = RunEmitter(run_id, agent_id=agent_id)
    _active_runs[conv.id] = run_id

    async def normalized() -> AsyncIterator[bytes]:
        """Normalize the developer backend's framework-native event stream into
        the rich internal schema and pipe it to the browser.

        Each upstream frame is `{"framework": "...", "event": <native event>}`.
        The matching translator (selected on the first frame) maps native events
        onto the shared `RunEmitter`; `run_start` / `run_end` and the envelope
        are synthesized here. The assistant turn is persisted from the emitter's
        accumulated final message.
        """
        translator = None
        end_events = None  # set once run_end is built (guards single call)
        try:
            # run_start, before any developer event.
            for ev in emitter.run_start(
                query=extract_query(input_payload), input=input_payload
            ):
                yield to_sse_frame(ev)

            async for frame in iter_frames(
                runtime_client.stream(agent_id, runtime_body)
            ):
                # Stop pulling on explicit cancel or a dropped client.
                if run_id in _cancelled_runs or await request.is_disconnected():
                    break
                data = frame.data_json
                if data is None:
                    continue

                # `{framework, event}` envelope; tolerate a bare native event.
                framework = data.get("framework") or "native"
                event = data.get("event", data)
                if isinstance(event, dict) and event.get("type") == "done":
                    break

                if translator is None:
                    translator = get_translator(framework)
                    if translator is None:
                        for ev in emitter.error(
                            f"Unsupported framework '{framework}'"
                        ):
                            yield to_sse_frame(ev)
                        break

                for ev in translator.handle(emitter, event):
                    yield to_sse_frame(ev)

            # run_end, synthesized at EOF/done — skipped on cancel or if the
            # client is already gone.
            if run_id not in _cancelled_runs and not await request.is_disconnected():
                end_events = emitter.run_end()
                for ev in end_events:
                    yield to_sse_frame(ev)
        finally:
            # Explicit cancel (the cancel route marked this run) → discard the
            # turn. A bare disconnect keeps the partial (original behavior).
            cancelled = run_id in _cancelled_runs
            _cancelled_runs.discard(run_id)
            if end_events is None:
                end_events = emitter.run_end()
            final_message = ""
            for ev in end_events:
                result = getattr(ev, "result", None)
                if result is not None:
                    final_message = result.message
            _active_runs.pop(conv.id, None)
            async with session_factory()() as bg:
                if cancelled:
                    # Roll the whole turn back: delete the user message persisted
                    # up-front and skip the partial assistant reply, so a
                    # cancelled exchange is never fed to the model next turn.
                    await bg.execute(
                        delete(Message).where(Message.id == user_message.id)
                    )
                else:
                    bg.add(
                        Message(
                            conversation_id=conv.id,
                            role="assistant",
                            content=final_message,
                            run_id=run_id,
                        )
                    )
                    # Bump updated_at on the parent conversation so the sidebar
                    # ordering reflects this exchange.
                    fresh_conv = await bg.get(Conversation, conv.id)
                    if fresh_conv is not None:
                        # SQLAlchemy onupdate fires only on UPDATE; touch a column.
                        fresh_conv.title = fresh_conv.title  # no-op flush trigger
                await bg.commit()

    return StreamingResponse(
        normalized(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering (nginx)
        },
    )


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

@router.post("/{conv_id}/cancel", response_model=CancelOut)
async def cancel(
    conv_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> CancelOut:
    conv = await _owned_conversation(session, user.id, conv_id)
    run_id = _active_runs.get(conv.id)
    if not run_id:
        return CancelOut(cancelled=False)
    # Mark the run cancelled so the chat stream rolls the turn back (drops the
    # user prompt + partial reply) — regardless of what the runtime reports.
    _cancelled_runs.add(run_id)
    result = await runtime_client.cancel(conv.agent_id, run_id)
    return CancelOut(cancelled=bool(result.get("cancelled", False)))


# ---------------------------------------------------------------------------
# Action proxy
# ---------------------------------------------------------------------------

@router.post("/{conv_id}/actions/{action_name}")
async def invoke_action(
    conv_id: uuid.UUID,
    action_name: str,
    body: ActionIn | None = None,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    conv = await _owned_conversation(session, user.id, conv_id)
    status_code, payload = await runtime_client.invoke_action(
        conv.agent_id, action_name, (body.args if body else None) or {}
    )
    from fastapi.responses import JSONResponse
    return JSONResponse(payload, status_code=status_code)
