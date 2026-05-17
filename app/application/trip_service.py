from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.application.dto import TripStartResult
from app.application.scoring.quote_scorer import normalize_ranking_priority
from app.domain.ports import IntentParserPort, ParsedIntent
from app.infrastructure.persistence.repositories import TripRepository, UserRepository


class TripService:
    def __init__(self, db: Session, intent_parser: IntentParserPort):
        self._users = UserRepository(db)
        self._trips = TripRepository(db)
        self._parser = intent_parser

    def start_trip(
        self,
        *,
        user_phone_e164: str | None,
        destination: str,
        check_in: date,
        check_out: date,
        guests: int,
        rooms: int,
        budget_total: float | None,
        currency: str,
        locale: str | None,
        ranking_priority: str | None = None,
    ) -> TripStartResult:
        user = self._users.create(phone_e164=user_phone_e164)
        trip = self._trips.create(
            user_id=user.id,
            destination=destination,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            rooms=rooms,
            budget_total=budget_total,
            currency=currency,
            locale=locale,
        )
        if ranking_priority:
            key = normalize_ranking_priority(ranking_priority)
            self._trips.merge_preferences(trip, preferences={"ranking_priority": key}, constraints={})
        return TripStartResult(trip_id=trip.id, user_id=user.id)

    def parse_and_store_intent(self, trip_id: uuid.UUID, user_text: str) -> ParsedIntent:
        parsed = self._parser.parse(user_text)
        trip = self._trips.get_required(trip_id)
        prefs = {**dict(trip.preferences or {}), **parsed.preferences}
        constraints = {**dict(trip.constraints or {}), **parsed.constraints}
        self._trips.save_preferences(trip, preferences=prefs, constraints=constraints)
        return parsed
