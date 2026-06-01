"""Importing this package registers every model on `Base.metadata`.

Alembic's `env.py` does `from platform_backend import models` for exactly this
side effect, so autogenerate sees every table.
"""

from .api_key import ApiKey  # noqa: F401
from .conversation import Conversation  # noqa: F401
from .folder import Folder  # noqa: F401
from .message import Message  # noqa: F401
from .user import User  # noqa: F401

__all__ = ["ApiKey", "Conversation", "Folder", "Message", "User"]
