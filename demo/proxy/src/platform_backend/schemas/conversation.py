from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    agent_id: str = Field(min_length=1, max_length=120)
    folder_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=200)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    # `folder_id` is set-or-unset via PATCH. `None` in the payload means
    # "leave it alone"; sending `null` explicitly to clear membership uses
    # an explicit sentinel below.
    folder_id: uuid.UUID | None = None
    clear_folder: bool = False


class ConversationOut(BaseModel):
    id: uuid.UUID
    agent_id: str
    folder_id: uuid.UUID | None
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
