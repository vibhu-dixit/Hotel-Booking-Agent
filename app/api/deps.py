from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.booking_service import BookingWorkflowService
from app.application.call_session_service import CallSessionService
from app.application.decision_service import DecisionService
from app.application.hotel_discovery_service import HotelDiscoveryService
from app.application.intent.rule_based_parser import RuleBasedIntentParser
from app.application.trip_service import TripService
from app.core.db import db_session
from app.infrastructure.audit.sqlalchemy_logger import SqlAlchemyAuditLogger

DbSession = Annotated[Session, Depends(db_session)]


def get_intent_parser() -> RuleBasedIntentParser:
    return RuleBasedIntentParser()


def get_audit_logger(db: DbSession) -> SqlAlchemyAuditLogger:
    return SqlAlchemyAuditLogger(db)


def get_trip_service(
    db: DbSession,
    parser: Annotated[RuleBasedIntentParser, Depends(get_intent_parser)],
) -> TripService:
    return TripService(db, parser)


def get_hotel_discovery(db: DbSession) -> HotelDiscoveryService:
    return HotelDiscoveryService(db)


def get_call_session_service(
    db: DbSession,
    audit: Annotated[SqlAlchemyAuditLogger, Depends(get_audit_logger)],
) -> CallSessionService:
    return CallSessionService(db, audit)


def get_decision_service(
    db: DbSession,
    audit: Annotated[SqlAlchemyAuditLogger, Depends(get_audit_logger)],
) -> DecisionService:
    return DecisionService(db, audit)


def get_booking_workflow(
    db: DbSession,
    audit: Annotated[SqlAlchemyAuditLogger, Depends(get_audit_logger)],
) -> BookingWorkflowService:
    return BookingWorkflowService(db, audit)
