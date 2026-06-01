from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessageIn(BaseModel):
    content: str = Field(min_length=1)


class CancelOut(BaseModel):
    cancelled: bool


class ActionIn(BaseModel):
    args: dict | None = None
