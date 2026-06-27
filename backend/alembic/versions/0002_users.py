"""users table (Phase 5 — Authentication).

Adds the ``users`` table: argon2 password hash + role + tenant seam.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-27
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_unique_constraint(
        "uq_users_tenant_username", "users", ["tenant_id", "username"]
    )


def downgrade() -> None:
    op.drop_table("users")
