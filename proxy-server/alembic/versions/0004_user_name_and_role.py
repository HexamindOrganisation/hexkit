"""Add name and role columns to users.

Both nullable: existing rows get None, new signups too. Populated either
via the demo-users loader (YAML) or the PATCH /me endpoint.

Revision ID: 0004_user_name_and_role
Revises: 0003_api_keys
Create Date: 2026-06-12
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0004_user_name_and_role"
down_revision: str | None = "0003_api_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(120), nullable=True))
    op.add_column("users", sa.Column("role", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "role")
    op.drop_column("users", "name")
