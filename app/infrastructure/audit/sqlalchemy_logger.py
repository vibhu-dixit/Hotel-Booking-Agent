from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import AuditEvent, AuditEventType


class SqlAlchemyAuditLogger:
    """Single place for audit writes (DRY)."""

    def __init__(self, db: Session):
        self._db = db

    def _emit(self, *, event_type: AuditEventType, user_id: uuid.UUID | None, trip_id: uuid.UUID | None, payload: dict) -> AuditEvent:
        evt = AuditEvent(
            user_id=user_id,
            trip_id=trip_id,
            event_type=event_type,
            payload=payload,
            created_at=datetime.utcnow(),
        )
        self._db.add(evt)
        self._db.commit()
        self._db.refresh(evt)
        return evt

    def log_call_started(self, *, user_id: uuid.UUID, trip_id: uuid.UUID, payload: dict) -> None:
        self._emit(event_type=AuditEventType.call_started, user_id=user_id, trip_id=trip_id, payload=payload)

    def log_decision_evaluated(self, *, trip_id: uuid.UUID, decision_id: uuid.UUID) -> None:
        self._emit(
            event_type=AuditEventType.decision_evaluated,
            user_id=None,
            trip_id=trip_id,
            payload={"decision_id": str(decision_id)},
        )

    def log_booking_approved(
        self, *, user_id: uuid.UUID, trip_id: uuid.UUID, quote_id: uuid.UUID, approval_id: uuid.UUID
    ) -> None:
        self._emit(
            event_type=AuditEventType.booking_approved,
            user_id=user_id,
            trip_id=trip_id,
            payload={"quote_id": str(quote_id), "approval_id": str(approval_id)},
        )

    def log_booking_attempted(self, *, user_id: uuid.UUID, trip_id: uuid.UUID, booking_id: uuid.UUID, quote_id: uuid.UUID) -> None:
        self._emit(
            event_type=AuditEventType.booking_attempted,
            user_id=user_id,
            trip_id=trip_id,
            payload={"booking_id": str(booking_id), "quote_id": str(quote_id)},
        )

    def log_consent_change(self, *, user_id: uuid.UUID, granted: bool, consent_type_value: str, text_version: str) -> None:
        self._emit(
            event_type=AuditEventType.consent_granted if granted else AuditEventType.consent_revoked,
            user_id=user_id,
            trip_id=None,
            payload={"consent_type": consent_type_value, "text_version": text_version},
        )
