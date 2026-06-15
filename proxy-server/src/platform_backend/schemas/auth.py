"""Request and response shapes for `/auth/*` and `/me`."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    name: str | None = None
    role: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MeUpdate(BaseModel):
    """Patchable profile fields. Either may be omitted (only the present
    keys are written); pass `null` to clear a field. Empty strings are
    coerced to None so a blank text input clears the value."""

    name: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, max_length=64)
