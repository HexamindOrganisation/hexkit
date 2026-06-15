from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AttachFilesIn(BaseModel):
    file_ids: list[uuid.UUID] = Field(default_factory=list)


class FileRenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class FileOut(BaseModel):
    id: uuid.UUID
    name: str
    mime: str
    size: int
    created_at: datetime

    model_config = {"from_attributes": True}
