"""init schema

Revision ID: 0001_init
Revises: 
Create Date: 2026-04-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    op.create_table(
        "users",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("phone_e164", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "trip_requests",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("destination", sa.String(length=256), nullable=False),
        sa.Column("check_in", sa.Date(), nullable=False),
        sa.Column("check_out", sa.Date(), nullable=False),
        sa.Column("guests", sa.Integer(), nullable=False),
        sa.Column("rooms", sa.Integer(), nullable=False),
        sa.Column("budget_total", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("locale", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trip_requests_user_id", "trip_requests", ["user_id"])

    op.create_table(
        "hotel_candidates",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("trip_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("place_id", sa.String(length=128), nullable=True),
        sa.Column("provider_ids", sa.JSON(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column("phone_e164", sa.String(length=32), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["trip_id"], ["trip_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trip_id", "place_id", name="uq_trip_place"),
    )
    op.create_index("ix_hotel_candidates_trip_id", "hotel_candidates", ["trip_id"])

    op.create_table(
        "call_sessions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("trip_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hotel_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Enum("created", "dialing", "in_progress", "completed", "failed", "cancelled", name="callstatus"), nullable=False),
        sa.Column("telephony_call_id", sa.String(length=128), nullable=True),
        sa.Column("caller_id_mode", sa.String(length=64), nullable=False),
        sa.Column("from_number", sa.String(length=32), nullable=True),
        sa.Column("to_number", sa.String(length=32), nullable=True),
        sa.Column("recording_enabled", sa.Boolean(), nullable=False),
        sa.Column("transcript_enabled", sa.Boolean(), nullable=False),
        sa.Column("audio_object_key", sa.String(length=512), nullable=True),
        sa.Column("transcript_object_key", sa.String(length=512), nullable=True),
        sa.Column("extracted_facts", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_candidates.id"]),
        sa.ForeignKeyConstraint(["trip_id"], ["trip_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_call_sessions_trip_id", "call_sessions", ["trip_id"])
    op.create_index("ix_call_sessions_hotel_id", "call_sessions", ["hotel_id"])
    op.create_index("ix_call_sessions_telephony_call_id", "call_sessions", ["telephony_call_id"])

    op.create_table(
        "quotes",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("trip_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hotel_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("call_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("room_type", sa.String(length=256), nullable=True),
        sa.Column("occupancy", sa.Integer(), nullable=True),
        sa.Column("nightly_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("taxes_fees", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("included_items", sa.JSON(), nullable=False),
        sa.Column("deposit", sa.JSON(), nullable=False),
        sa.Column("cancellation", sa.JSON(), nullable=False),
        sa.Column("check_in_out", sa.JSON(), nullable=False),
        sa.Column("quote_valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("raw_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["call_id"], ["call_sessions.id"]),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_candidates.id"]),
        sa.ForeignKeyConstraint(["trip_id"], ["trip_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quotes_trip_id", "quotes", ["trip_id"])
    op.create_index("ix_quotes_hotel_id", "quotes", ["hotel_id"])

    op.create_table(
        "decision_results",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("trip_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("ranked", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["trip_id"], ["trip_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_decision_results_trip_id", "decision_results", ["trip_id"])

    op.create_table(
        "booking_approvals",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trip_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_text_version", sa.String(length=64), nullable=False),
        sa.Column("approval_payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"]),
        sa.ForeignKeyConstraint(["trip_id"], ["trip_requests.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "quote_id", name="uq_user_quote_approval"),
    )
    op.create_index("ix_booking_approvals_user_id", "booking_approvals", ["user_id"])
    op.create_index("ix_booking_approvals_trip_id", "booking_approvals", ["trip_id"])
    op.create_index("ix_booking_approvals_quote_id", "booking_approvals", ["quote_id"])

    op.create_table(
        "booking_records",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("trip_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Enum("pending", "attempted", "confirmed", "failed", "cancelled", name="bookingstatus"), nullable=False),
        sa.Column("confirmation_number", sa.String(length=128), nullable=True),
        sa.Column("final_terms", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"]),
        sa.ForeignKeyConstraint(["trip_id"], ["trip_requests.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_booking_records_trip_id", "booking_records", ["trip_id"])
    op.create_index("ix_booking_records_user_id", "booking_records", ["user_id"])
    op.create_index("ix_booking_records_quote_id", "booking_records", ["quote_id"])

    op.create_table(
        "user_consents",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consent_type", sa.Enum("outbound_calls", "caller_id_use", "recording_transcription", "booking_by_phone", name="consenttype"), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("text_version", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "consent_type", name="uq_user_consent_type"),
    )
    op.create_index("ix_user_consents_user_id", "user_consents", ["user_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trip_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "event_type",
            sa.Enum(
                "consent_granted",
                "consent_revoked",
                "call_started",
                "call_ended",
                "quote_extracted",
                "decision_evaluated",
                "booking_approved",
                "booking_attempted",
                "booking_confirmed",
                "booking_failed",
                name="auditeventtype",
            ),
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["trip_id"], ["trip_requests.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])
    op.create_index("ix_audit_events_trip_id", "audit_events", ["trip_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_index("ix_audit_events_trip_id", table_name="audit_events")
    op.drop_index("ix_audit_events_user_id", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_user_consents_user_id", table_name="user_consents")
    op.drop_table("user_consents")

    op.drop_index("ix_booking_records_quote_id", table_name="booking_records")
    op.drop_index("ix_booking_records_user_id", table_name="booking_records")
    op.drop_index("ix_booking_records_trip_id", table_name="booking_records")
    op.drop_table("booking_records")

    op.drop_index("ix_booking_approvals_quote_id", table_name="booking_approvals")
    op.drop_index("ix_booking_approvals_trip_id", table_name="booking_approvals")
    op.drop_index("ix_booking_approvals_user_id", table_name="booking_approvals")
    op.drop_table("booking_approvals")

    op.drop_index("ix_decision_results_trip_id", table_name="decision_results")
    op.drop_table("decision_results")

    op.drop_index("ix_quotes_hotel_id", table_name="quotes")
    op.drop_index("ix_quotes_trip_id", table_name="quotes")
    op.drop_table("quotes")

    op.drop_index("ix_call_sessions_telephony_call_id", table_name="call_sessions")
    op.drop_index("ix_call_sessions_hotel_id", table_name="call_sessions")
    op.drop_index("ix_call_sessions_trip_id", table_name="call_sessions")
    op.drop_table("call_sessions")

    op.drop_index("ix_hotel_candidates_trip_id", table_name="hotel_candidates")
    op.drop_table("hotel_candidates")

    op.drop_index("ix_trip_requests_user_id", table_name="trip_requests")
    op.drop_table("trip_requests")

    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS auditeventtype;")
    op.execute("DROP TYPE IF EXISTS consenttype;")
    op.execute("DROP TYPE IF EXISTS bookingstatus;")
    op.execute("DROP TYPE IF EXISTS callstatus;")

