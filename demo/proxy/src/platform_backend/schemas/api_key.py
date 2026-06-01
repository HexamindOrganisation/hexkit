from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# Closed vocabulary — matches the runtime's framework set today (TODO line 87).
# Extending = add a new value here and a passthrough in `Credentials` (runtime
# protocol.py).
Provider = Literal["openai", "anthropic", "google"]


class ApiKeyIn(BaseModel):
    value: str = Field(min_length=1, max_length=2048)


class ApiKeyOut(BaseModel):
    """Presence-only view. The actual value is never returned over the wire."""

    provider: Provider
    present: bool = True
    updated_at: datetime
