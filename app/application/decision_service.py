from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.application.scoring.quote_scorer import QuoteScorer
from app.db.models import DecisionResult
from app.infrastructure.audit.sqlalchemy_logger import SqlAlchemyAuditLogger
from app.infrastructure.persistence.repositories import DecisionRepository, HotelRepository, QuoteRepository, TripRepository


class DecisionService:
    """Ranks quotes for a trip and persists a decision snapshot."""

    def __init__(
        self,
        db: Session,
        audit: SqlAlchemyAuditLogger,
        scorer: QuoteScorer | None = None,
    ):
        self._trips = TripRepository(db)
        self._quotes = QuoteRepository(db)
        self._hotels = HotelRepository(db)
        self._decisions = DecisionRepository(db)
        self._audit = audit
        self._scorer = scorer or QuoteScorer()

    def evaluate(self, trip_id: uuid.UUID) -> DecisionResult:
        trip = self._trips.get_required(trip_id)
        quotes = self._quotes.list_for_trip(trip_id)
        hotels = {h.id: h for h in self._hotels.list_for_trip(trip_id)}

        ranked: list[dict] = []
        for q in quotes:
            h = hotels.get(q.hotel_id)
            if h is None:
                continue
            score, reasons = self._scorer.score(trip, h, q)
            ranked.append(
                {
                    "quote_id": str(q.id),
                    "hotel_id": str(h.id),
                    "hotel_name": h.name,
                    "score": score,
                    "total_price": float(q.total_price) if q.total_price is not None else None,
                    "currency": q.currency,
                    "explain": reasons,
                }
            )

        ranked.sort(key=lambda x: x["score"], reverse=True)

        decision = DecisionResult(trip_id=trip_id, algorithm_version="v1", ranked=ranked)
        saved = self._decisions.save(decision)

        self._audit.log_decision_evaluated(trip_id=trip_id, decision_id=saved.id)
        return saved
