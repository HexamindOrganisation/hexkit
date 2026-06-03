"""User file library: upload / list / fetch / delete. Files are global to the
user (reusable across conversations) and stored as bytes in the DB. They're
used as chat attachments — the chat route forwards selected files to the agent
backend as `context.files`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.implicit_user import current_user
from ..db import get_session
from ..models.file import File as FileModel
from ..models.user import User
from ..schemas.file import FileOut


router = APIRouter(prefix="/files", tags=["files"])

# v1 cap — files are inlined into requests, so keep them modest.
MAX_FILE_BYTES = 5 * 1024 * 1024


async def _get_owned(
    session: AsyncSession, user_id: uuid.UUID, file_id: uuid.UUID
) -> FileModel:
    f = await session.get(FileModel, file_id)
    if f is None or f.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="file not found"
        )
    return f


@router.get("", response_model=list[FileOut])
async def list_files(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[FileOut]:
    result = await session.execute(
        select(FileModel)
        .where(FileModel.user_id == user.id)
        .order_by(FileModel.created_at.desc())
    )
    return [FileOut.model_validate(f) for f in result.scalars().all()]


@router.post("", response_model=FileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> FileOut:
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"file exceeds {MAX_FILE_BYTES} bytes",
        )
    row = FileModel(
        user_id=user.id,
        name=file.filename or "untitled",
        mime=file.content_type or "application/octet-stream",
        size=len(data),
        content=data,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return FileOut.model_validate(row)


@router.get("/{file_id}")
async def get_file(
    file_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    f = await _get_owned(session, user.id, file_id)
    return Response(
        content=f.content,
        media_type=f.mime,
        headers={"Content-Disposition": f'inline; filename="{f.name}"'},
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    f = await _get_owned(session, user.id, file_id)
    await session.delete(f)
    await session.commit()
