from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    run_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
