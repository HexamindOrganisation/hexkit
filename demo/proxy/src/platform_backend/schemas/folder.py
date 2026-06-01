from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)


class FolderOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
