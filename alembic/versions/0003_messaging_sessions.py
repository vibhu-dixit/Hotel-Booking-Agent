"""messaging sessions + linq webhook dedup

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-28

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0003"
down_revision = "0002_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "linq_webhook_events",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )

    op.create_table(
        "messaging_sessions",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("trip_id", UUID(as_uuid=True), nullable=True),
        sa.Column("linq_chat_id", sa.String(length=128), nullable=False),
        sa.Column("phase", sa.String(length=64), nullable=False, server_default="collecting_intent"),
        sa.Column("selected_hotel_id", UUID(as_uuid=True), nullable=True),
        sa.Column("selected_quote_id", UUID(as_uuid=True), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trip_requests.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["selected_hotel_id"], ["hotel_candidates.id"]),
        sa.ForeignKeyConstraint(["selected_quote_id"], ["quotes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messaging_sessions_user_id", "messaging_sessions", ["user_id"])
    op.create_index("ix_messaging_sessions_linq_chat_id", "messaging_sessions", ["linq_chat_id"], unique=True)

    op.create_index("ix_users_phone_e164", "users", ["phone_e164"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_phone_e164", table_name="users")
    op.drop_index("ix_messaging_sessions_linq_chat_id", table_name="messaging_sessions")
    op.drop_index("ix_messaging_sessions_user_id", table_name="messaging_sessions")
    op.drop_table("messaging_sessions")
    op.drop_table("linq_webhook_events")
