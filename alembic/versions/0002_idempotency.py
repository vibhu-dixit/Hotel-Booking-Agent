"""add idempotency keys

Revision ID: 0002_idempotency
Revises: 0001_init
Create Date: 2026-04-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0002_idempotency"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("route", sa.String(length=256), nullable=False),
        sa.Column("request_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.Enum("started", "completed", "failed", name="idempotencystatus"), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", "route", name="uq_idempotency_key_route"),
    )
    op.create_index("ix_idempotency_keys_user_id", "idempotency_keys", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_keys_user_id", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
    op.execute("DROP TYPE IF EXISTS idempotencystatus;")

