from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConsentType(str, enum.Enum):
    outbound_calls = "outbound_calls"
    caller_id_use = "caller_id_use"
    recording_transcription = "recording_transcription"
    booking_by_phone = "booking_by_phone"


class AuditEventType(str, enum.Enum):
    consent_granted = "consent_granted"
    consent_revoked = "consent_revoked"
    call_started = "call_started"
    call_ended = "call_ended"
    quote_extracted = "quote_extracted"
    decision_evaluated = "decision_evaluated"
    booking_approved = "booking_approved"
    booking_attempted = "booking_attempted"
    booking_confirmed = "booking_confirmed"
    booking_failed = "booking_failed"


class CallStatus(str, enum.Enum):
    created = "created"
    dialing = "dialing"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class BookingStatus(str, enum.Enum):
    pending = "pending"
    attempted = "attempted"
    confirmed = "confirmed"
    failed = "failed"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_e164: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class TripRequest(Base):
    __tablename__ = "trip_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)

    destination: Mapped[str] = mapped_column(String(256))
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date] = mapped_column(Date)
    guests: Mapped[int] = mapped_column(Integer)
    rooms: Mapped[int] = mapped_column(Integer, default=1)
    budget_total: Mapped[Numeric | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD")

    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    locale: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped["User"] = relationship()


class MessagingSession(Base):
    """Maps a Linq chat to an in-flight booking workflow."""

    __tablename__ = "messaging_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    trip_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trip_requests.id"), nullable=True)
    linq_chat_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    phase: Mapped[str] = mapped_column(String(64), default="collecting_intent")
    selected_hotel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotel_candidates.id"), nullable=True
    )
    selected_quote_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("quotes.id"), nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class LinqWebhookDedup(Base):
    __tablename__ = "linq_webhook_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class HotelCandidate(Base):
    __tablename__ = "hotel_candidates"
    __table_args__ = (UniqueConstraint("trip_id", "place_id", name="uq_trip_place"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trip_requests.id"), index=True)

    place_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_ids: Mapped[dict] = mapped_column(JSON, default=dict)

    name: Mapped[str] = mapped_column(String(256))
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    phone_e164: Mapped[str | None] = mapped_column(String(32), nullable=True)

    extra_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    trip: Mapped["TripRequest"] = relationship()


class CallSession(Base):
    __tablename__ = "call_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trip_requests.id"), index=True)
    hotel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hotel_candidates.id"), index=True)

    status: Mapped[CallStatus] = mapped_column(Enum(CallStatus), default=CallStatus.created)
    telephony_call_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    caller_id_mode: Mapped[str] = mapped_column(String(64), default="verified_business_number")
    from_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_number: Mapped[str | None] = mapped_column(String(32), nullable=True)

    recording_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    transcript_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    audio_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    transcript_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    extracted_facts: Mapped[dict] = mapped_column(JSON, default=dict)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    trip: Mapped["TripRequest"] = relationship()
    hotel: Mapped["HotelCandidate"] = relationship()


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trip_requests.id"), index=True)
    hotel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hotel_candidates.id"), index=True)
    call_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("call_sessions.id"), nullable=True)

    source: Mapped[str] = mapped_column(String(32), default="call")
    room_type: Mapped[str | None] = mapped_column(String(256), nullable=True)
    occupancy: Mapped[int | None] = mapped_column(Integer, nullable=True)

    nightly_rate: Mapped[Numeric | None] = mapped_column(Numeric(12, 2), nullable=True)
    taxes_fees: Mapped[Numeric | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_price: Mapped[Numeric | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD")

    included_items: Mapped[dict] = mapped_column(JSON, default=dict)
    deposit: Mapped[dict] = mapped_column(JSON, default=dict)
    cancellation: Mapped[dict] = mapped_column(JSON, default=dict)
    check_in_out: Mapped[dict] = mapped_column(JSON, default=dict)
    quote_valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0)

    raw_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    trip: Mapped["TripRequest"] = relationship()
    hotel: Mapped["HotelCandidate"] = relationship()


class DecisionResult(Base):
    __tablename__ = "decision_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trip_requests.id"), index=True)
    algorithm_version: Mapped[str] = mapped_column(String(64), default="v1")
    ranked: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class BookingApproval(Base):
    __tablename__ = "booking_approvals"
    __table_args__ = (UniqueConstraint("user_id", "quote_id", name="uq_user_quote_approval"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trip_requests.id"), index=True)
    quote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quotes.id"), index=True)

    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    approval_text_version: Mapped[str] = mapped_column(String(64), default="v1")
    approval_payload: Mapped[dict] = mapped_column(JSON, default=dict)


class BookingRecord(Base):
    __tablename__ = "booking_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trip_requests.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    quote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quotes.id"), index=True)

    status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus), default=BookingStatus.pending)
    confirmation_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    final_terms: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class UserConsent(Base):
    __tablename__ = "user_consents"
    __table_args__ = (UniqueConstraint("user_id", "consent_type", name="uq_user_consent_type"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    consent_type: Mapped[ConsentType] = mapped_column(Enum(ConsentType))
    granted: Mapped[bool] = mapped_column(Boolean, default=False)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    text_version: Mapped[str] = mapped_column(String(64), default="v1")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    trip_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trip_requests.id"), nullable=True, index=True)
    event_type: Mapped[AuditEventType] = mapped_column(Enum(AuditEventType), index=True)

    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class IdempotencyStatus(str, enum.Enum):
    started = "started"
    completed = "completed"
    failed = "failed"


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("key", "route", name="uq_idempotency_key_route"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    route: Mapped[str] = mapped_column(String(256), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[IdempotencyStatus] = mapped_column(Enum(IdempotencyStatus), default=IdempotencyStatus.started)
    response_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

