"""User account model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # Lowercased at write time (see `routes/auth.py`); unique index enforces
    # one account per email without requiring the citext extension.
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Display name. Optional — falls back to the email's local-part in the UI.
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Opaque role string forwarded to hexgate-wrapped agents as
    # `context.user.role`. HexUI never interprets it; each dev team decides
    # their own role vocabulary.
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
