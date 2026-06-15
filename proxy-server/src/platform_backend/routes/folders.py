"""Folder CRUD. Flat — no parent_id in v0.

Ownership is enforced by always filtering on `user_id` from the JWT. A
resource owned by another user returns 404, not 403, to avoid leaking which
ids exist. Same pattern as conversations and messages.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import current_user
from ..db import get_session
from ..models.folder import Folder
from ..models.user import User
from ..schemas.folder import FolderCreate, FolderOut, FolderUpdate

router = APIRouter(prefix="/folders", tags=["folders"])


async def _get_owned(
    session: AsyncSession, user_id: uuid.UUID, folder_id: uuid.UUID
) -> Folder:
    folder = await session.get(Folder, folder_id)
    if folder is None or folder.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="folder not found")
    return folder


@router.get("", response_model=list[FolderOut])
async def list_folders(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[FolderOut]:
    result = await session.execute(
        select(Folder).where(Folder.user_id == user.id).order_by(Folder.name)
    )
    return [FolderOut.model_validate(f) for f in result.scalars().all()]


@router.post("", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
async def create_folder(
    body: FolderCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> FolderOut:
    folder = Folder(user_id=user.id, name=body.name)
    session.add(folder)
    await session.commit()
    await session.refresh(folder)
    return FolderOut.model_validate(folder)


@router.patch("/{folder_id}", response_model=FolderOut)
async def update_folder(
    folder_id: uuid.UUID,
    body: FolderUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> FolderOut:
    folder = await _get_owned(session, user.id, folder_id)
    if body.name is not None:
        folder.name = body.name
    await session.commit()
    await session.refresh(folder)
    return FolderOut.model_validate(folder)


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    folder = await _get_owned(session, user.id, folder_id)
    await session.delete(folder)
    await session.commit()
