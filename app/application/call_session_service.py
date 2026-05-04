from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import CallSession, CallStatus
from app.infrastructure.audit.sqlalchemy_logger import SqlAlchemyAuditLogger
from app.infrastructure.persistence.repositories import CallSessionRepository, HotelRepository, TripRepository


class CallSessionService:
    """Creates call session records (MVP: no live telephony)."""

    def __init__(self, db: Session, audit: SqlAlchemyAuditLogger):
        self._trips = TripRepository(db)
        self._hotels = HotelRepository(db)
        self._calls = CallSessionRepository(db)
        self._audit = audit

    def start(
        self, *, trip_id: uuid.UUID, hotel_id: uuid.UUID, recording_enabled: bool
    ) -> CallSession:
        trip = self._trips.get_required(trip_id)
        hotel = self._hotels.get_required(hotel_id)

        call = CallSession(
            trip_id=trip.id,
            hotel_id=hotel.id,
            status=CallStatus.created,
            telephony_call_id=None,
            caller_id_mode=settings.caller_id_mode,
            from_number=settings.linq_from_number,
            to_number=hotel.phone_e164,
            recording_enabled=recording_enabled,
            transcript_enabled=True,
            extracted_facts={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        saved = self._calls.save(call)

        self._audit.log_call_started(
            user_id=trip.user_id,
            trip_id=trip_id,
            payload={
                "call_id": str(saved.id),
                "hotel_id": str(hotel_id),
                "recording_enabled": recording_enabled,
            },
        )
        return saved

    def get_status(self, call_id: uuid.UUID) -> CallSession:
        return self._calls.get_required(call_id)
