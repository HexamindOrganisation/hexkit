"""Per-user, per-provider encrypted API key.

The ciphertext column stores the Fernet envelope (see `crypto/fernet.py`).
Plaintext never lives in the database, on the wire, or in logs.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # One of {"openai", "anthropic", "google"}. Validated at the route boundary
    # so the column type can stay portable (no Postgres-only ENUM type — the
    # Literal in the schema does the work).
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_api_keys_user_provider"),
    )
