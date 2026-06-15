from __future__ import annotations

from pydantic import BaseModel, Field


class ContextItemIn(BaseModel):
    """Payload for toggling a widget's content into a conversation's context."""

    label: str = Field(min_length=1, max_length=300)
    mime: str = Field(default="text/plain", max_length=100)
    content: str


class ContextKeyOut(BaseModel):
    """Light listing — which widgets are in context (for restoring toggle state)."""

    key: str
    label: str
