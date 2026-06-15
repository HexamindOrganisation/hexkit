from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class ChatMessageIn(BaseModel):
    content: str = Field(min_length=1)
    # Files newly attached on this turn. They're LINKED to the conversation
    # (persisted), then every turn forwards all of the conversation's files.
    file_ids: list[uuid.UUID] = Field(default_factory=list)


class CancelOut(BaseModel):
    cancelled: bool


class ActionIn(BaseModel):
    args: dict | None = None
