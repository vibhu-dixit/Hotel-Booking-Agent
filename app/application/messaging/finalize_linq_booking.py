from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.application.booking_service import BookingWorkflowService
from app.db.models import BookingRecord, BookingStatus
from app.infrastructure.audit.sqlalchemy_logger import SqlAlchemyAuditLogger
from app.infrastructure.persistence.repositories import (
    BookingRecordRepository,
    CallSessionRepository,
    QuoteRepository,
)


def finalize_hold_after_approval(
    db: Session,
    *,
    user_id: uuid.UUID,
    trip_id: uuid.UUID,
    quote_id: uuid.UUID,
) -> tuple[BookingRecord, str | None]:
    """
    Record consent approval, create booking, attach confirmation from simulated/call facts when present.
    Single entry point for Linq YES flow (DRY with orchestration policy).
    """
    audit = SqlAlchemyAuditLogger(db)
    bw = BookingWorkflowService(db, audit)
    quotes = QuoteRepository(db)
    calls = CallSessionRepository(db)
    bookings = BookingRecordRepository(db)

    bw.record_approval(
        user_id=user_id,
        trip_id=trip_id,
        quote_id=quote_id,
        approval_text_version="v1",
        approval_payload={"channel": "linq"},
    )
    booking = bw.create_booking(user_id=user_id, trip_id=trip_id, quote_id=quote_id)

    quote = quotes.get_required_for_trip(trip_id, quote_id)
    conf: str | None = None
    if quote.call_id:
        call = calls.get_required(quote.call_id)
        raw = call.extracted_facts.get("hold_confirmation")
        if raw:
            conf = str(raw)[:128]

    status = BookingStatus.confirmed if conf else BookingStatus.attempted
    bookings.patch(booking, confirmation_number=conf, status=status)
    return booking, conf
