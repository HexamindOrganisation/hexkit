"""Conversation CRUD.

Ownership rules: a conversation belongs to `user_id`. To move a conversation
into a folder via PATCH, the folder must also belong to the same user, or
the PATCH returns 404 for the folder. Messages are read-only here (writes
go through the chat route, Phase C.4).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.implicit_user import current_user
from ..db import get_session
from ..models.conversation import Conversation
from ..models.folder import Folder
from ..models.message import Message
from ..models.user import User
from ..schemas.conversation import (
    ConversationCreate,
    ConversationOut,
    ConversationUpdate,
)
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
