from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.exceptions import ApprovalRequiredError
from app.db.models import BookingApproval, BookingRecord, BookingStatus
from app.infrastructure.audit.sqlalchemy_logger import SqlAlchemyAuditLogger
from app.infrastructure.persistence.repositories import (
    BookingApprovalRepository,
    BookingRecordRepository,
    QuoteRepository,
    TripRepository,
)


class BookingWorkflowService:
    """Explicit approval gate + booking record creation."""

    def __init__(self, db: Session, audit: SqlAlchemyAuditLogger):
        self._trips = TripRepository(db)
        self._quotes = QuoteRepository(db)
        self._approvals = BookingApprovalRepository(db)
        self._bookings = BookingRecordRepository(db)
        self._audit = audit

    def record_approval(
        self,
        *,
        user_id: uuid.UUID,
        trip_id: uuid.UUID,
        quote_id: uuid.UUID,
        approval_text_version: str,
        approval_payload: dict,
    ) -> BookingApproval:
        approval = BookingApproval(
            user_id=user_id,
            trip_id=trip_id,
            quote_id=quote_id,
            approved_at=datetime.utcnow(),
            approval_text_version=approval_text_version,
            approval_payload=approval_payload,
        )
        saved = self._approvals.save(approval)

        self._audit.log_booking_approved(
            user_id=user_id,
            trip_id=trip_id,
            quote_id=quote_id,
            approval_id=saved.id,
        )
        return saved

    def create_booking(self, *, user_id: uuid.UUID, trip_id: uuid.UUID, quote_id: uuid.UUID) -> BookingRecord:
        self._trips.get_required(trip_id)
        self._quotes.get_required_for_trip(trip_id, quote_id)

        approval = self._approvals.find_by_user_trip_quote(user_id=user_id, trip_id=trip_id, quote_id=quote_id)
        if approval is None:
            raise ApprovalRequiredError("Booking requires explicit approval for this quote.")

        booking = BookingRecord(
            trip_id=trip_id,
            user_id=user_id,
            quote_id=quote_id,
            status=BookingStatus.attempted,
            confirmation_number=None,
            final_terms={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        saved = self._bookings.save(booking)

        self._audit.log_booking_attempted(
            user_id=user_id,
            trip_id=trip_id,
            booking_id=saved.id,
            quote_id=quote_id,
        )
        return saved

    def get_booking(self, booking_id: uuid.UUID) -> BookingRecord:
        return self._bookings.get_required(booking_id)
