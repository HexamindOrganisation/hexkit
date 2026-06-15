"""Conversation CRUD.

Ownership rules: a conversation belongs to `user_id`. To move a conversation
into a folder via PATCH, the folder must also belong to the same user, or
the PATCH returns 404 for the folder. Messages are read-only here (writes
go through the chat route, Phase C.4).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import current_user
from ..db import get_session
from ..models.conversation import Conversation
from ..models.conversation_context import ConversationContext
from ..models.conversation_file import ConversationFile
from ..models.file import File as FileModel
from ..models.folder import Folder
from ..models.message import Message
from ..models.user import User
from ..schemas.context import ContextItemIn, ContextKeyOut
from ..schemas.conversation import (
    ConversationCreate,
    ConversationOut,
    ConversationUpdate,
)
from ..schemas.file import AttachFilesIn, FileOut
from ..schemas.message import MessageOut

router = APIRouter(prefix="/conversations", tags=["conversations"])


async def _get_owned(
    session: AsyncSession, user_id: uuid.UUID, conv_id: uuid.UUID
) -> Conversation:
    conv = await session.get(Conversation, conv_id)
    if conv is None or conv.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found"
        )
    return conv


async def _verify_folder(
    session: AsyncSession, user_id: uuid.UUID, folder_id: uuid.UUID | None
) -> None:
    if folder_id is None:
        return
    folder = await session.get(Folder, folder_id)
    if folder is None or folder.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="folder not found"
        )


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ConversationOut]:
    # Newest-first by activity, not creation; matches the sidebar reading order.
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return [ConversationOut.model_validate(c) for c in result.scalars().all()]


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ConversationOut:
    await _verify_folder(session, user.id, body.folder_id)
    conv = Conversation(
        user_id=user.id,
        agent_id=body.agent_id,
        folder_id=body.folder_id,
        title=body.title,
    )
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return ConversationOut.model_validate(conv)


@router.patch("/{conv_id}", response_model=ConversationOut)
async def update_conversation(
    conv_id: uuid.UUID,
    body: ConversationUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ConversationOut:
    conv = await _get_owned(session, user.id, conv_id)
    if body.title is not None:
        conv.title = body.title
    if body.clear_folder:
        conv.folder_id = None
    elif body.folder_id is not None:
        await _verify_folder(session, user.id, body.folder_id)
        conv.folder_id = body.folder_id
    await session.commit()
    await session.refresh(conv)
    return ConversationOut.model_validate(conv)


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conv_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    conv = await _get_owned(session, user.id, conv_id)
    await session.delete(conv)
    await session.commit()


@router.get("/{conv_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conv_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[MessageOut]:
    await _get_owned(session, user.id, conv_id)  # ownership check
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at)
    )
    return [MessageOut.model_validate(m) for m in result.scalars().all()]


# ---------------------------------------------------------------------------
# Conversation attachments (files persist across turns within a conversation)
# ---------------------------------------------------------------------------

async def conversation_files(
    session: AsyncSession, conv_id: uuid.UUID
) -> list[FileModel]:
    """All files linked to a conversation, newest-attached first."""
    result = await session.execute(
        select(FileModel)
        .join(ConversationFile, ConversationFile.file_id == FileModel.id)
        .where(ConversationFile.conversation_id == conv_id)
        .order_by(ConversationFile.created_at)
    )
    return list(result.scalars().all())


async def link_files(
    session: AsyncSession,
    conv_id: uuid.UUID,
    user_id: uuid.UUID,
    file_ids: list[uuid.UUID],
) -> None:
    """Idempotently link user-owned files to a conversation. Unknown / other
    users' ids are silently ignored. Caller commits."""
    if not file_ids:
        return
    owned = (
        await session.execute(
            select(FileModel.id).where(
                FileModel.user_id == user_id, FileModel.id.in_(file_ids)
            )
        )
    ).scalars().all()
    existing = set(
        (
            await session.execute(
                select(ConversationFile.file_id).where(
                    ConversationFile.conversation_id == conv_id
                )
            )
        ).scalars().all()
    )
    for fid in owned:
        if fid not in existing:
            session.add(ConversationFile(conversation_id=conv_id, file_id=fid))


@router.get("/{conv_id}/files", response_model=list[FileOut])
async def list_conversation_files(
    conv_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[FileOut]:
    await _get_owned(session, user.id, conv_id)
    return [FileOut.model_validate(f) for f in await conversation_files(session, conv_id)]


@router.post("/{conv_id}/files", response_model=list[FileOut])
async def attach_conversation_files(
    conv_id: uuid.UUID,
    body: AttachFilesIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[FileOut]:
    await _get_owned(session, user.id, conv_id)
    await link_files(session, conv_id, user.id, body.file_ids)
    await session.commit()
    return [FileOut.model_validate(f) for f in await conversation_files(session, conv_id)]


@router.delete("/{conv_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_conversation_file(
    conv_id: uuid.UUID,
    file_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await _get_owned(session, user.id, conv_id)
    await session.execute(
        delete(ConversationFile).where(
            ConversationFile.conversation_id == conv_id,
            ConversationFile.file_id == file_id,
        )
    )
    await session.commit()


# ---------------------------------------------------------------------------
# Conversation context items (widget content toggled into the model's context)
# ---------------------------------------------------------------------------

async def conversation_context_items(
    session: AsyncSession, conv_id: uuid.UUID
) -> list[ConversationContext]:
    """All context items toggled on for a conversation, oldest-first."""
    result = await session.execute(
        select(ConversationContext)
        .where(ConversationContext.conversation_id == conv_id)
        .order_by(ConversationContext.updated_at)
    )
    return list(result.scalars().all())


@router.get("/{conv_id}/context", response_model=list[ContextKeyOut])
async def list_conversation_context(
    conv_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ContextKeyOut]:
    await _get_owned(session, user.id, conv_id)
    items = await conversation_context_items(session, conv_id)
    return [ContextKeyOut(key=i.key, label=i.label) for i in items]


@router.put("/{conv_id}/context/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def set_conversation_context(
    conv_id: uuid.UUID,
    key: str,
    body: ContextItemIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Upsert a widget's content into the conversation's context (toggle on /
    re-sync). Keyed by `key` (the widget name) so it's idempotent."""
    await _get_owned(session, user.id, conv_id)
    existing = (
        await session.execute(
            select(ConversationContext).where(
                ConversationContext.conversation_id == conv_id,
                ConversationContext.key == key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.label = body.label
        existing.mime = body.mime
        existing.content = body.content
    else:
        session.add(
            ConversationContext(
                conversation_id=conv_id,
                key=key,
                label=body.label,
                mime=body.mime,
                content=body.content,
            )
        )
    await session.commit()


@router.delete("/{conv_id}/context/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_conversation_context(
    conv_id: uuid.UUID,
    key: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await _get_owned(session, user.id, conv_id)
    await session.execute(
        delete(ConversationContext).where(
            ConversationContext.conversation_id == conv_id,
            ConversationContext.key == key,
        )
    )
    await session.commit()
