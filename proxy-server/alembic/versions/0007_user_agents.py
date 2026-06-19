"""Add users.agents — per-user agent allow-list.

`NULL` = unrestricted (every agent in the roster); a non-empty JSON list scopes
the user to exactly those agent ids. See `platform_backend/access.py`.

Revision ID: 0007_user_agents
Revises: 0006_drop_api_keys
Create Date: 2026-06-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0007_user_agents"
down_revision: Union[str, None] = "0006_drop_api_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("agents", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "agents")
