from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ConsentType, UserConsent
from app.infrastructure.audit.sqlalchemy_logger import SqlAlchemyAuditLogger


class ConsentService:
    """User consent records with audit trail."""

    def __init__(self, db: Session, audit: SqlAlchemyAuditLogger):
        self._db = db
        self._audit = audit

    def set_consent(
        self,
        *,
        user_id: uuid.UUID,
        consent_type: ConsentType,
        granted: bool,
        text_version: str = "v1",
    ) -> UserConsent:
        existing = self._db.execute(
            select(UserConsent).where(UserConsent.user_id == user_id, UserConsent.consent_type == consent_type)
        ).scalar_one_or_none()

        now = datetime.utcnow()
        if existing is None:
            existing = UserConsent(
                user_id=user_id,
                consent_type=consent_type,
                granted=granted,
                granted_at=now if granted else None,
                revoked_at=None if granted else now,
                text_version=text_version,
            )
            self._db.add(existing)
        else:
            existing.granted = granted
            existing.text_version = text_version
            if granted:
                existing.granted_at = now
                existing.revoked_at = None
            else:
                existing.revoked_at = now

        self._db.commit()
        self._db.refresh(existing)

        self._audit.log_consent_change(
            user_id=user_id,
            granted=granted,
            consent_type_value=consent_type.value,
            text_version=text_version,
        )
        return existing

    def require_consent(self, *, user_id: uuid.UUID, consent_type: ConsentType) -> None:
        consent = self._db.execute(
            select(UserConsent).where(UserConsent.user_id == user_id, UserConsent.consent_type == consent_type)
        ).scalar_one_or_none()
        if consent is None or not consent.granted:
            raise PermissionError(f"Missing required consent: {consent_type.value}")
