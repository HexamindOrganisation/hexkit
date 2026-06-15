"""Conversation context items — text a widget (table / markdown) toggled into
the model's context. Conversation-scoped and persistent across turns, like file
attachments: every turn forwards all of a conversation's context items to the
agent backend (merged into `context.files`). Keyed by the widget's name so the
toggle is idempotent (one item per widget per conversation)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class ConversationContext(Base):
    __tablename__ = "conversation_context"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # The widget's name — stable per ui.yaml, so toggling upserts the same row.
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    # Human/model-facing label, e.g. "team-roster.csv (table)".
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    mime: Mapped[str] = mapped_column(String(100), nullable=False, default="text/plain")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
