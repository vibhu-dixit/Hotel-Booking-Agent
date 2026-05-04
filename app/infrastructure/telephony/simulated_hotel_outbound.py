from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.application.call_session_service import CallSessionService
from app.core.config import settings
from app.db.models import CallSession, CallStatus, HotelCandidate, Quote, TripRequest
from app.infrastructure.ai.nvidia_llm import chat_response_text
from app.infrastructure.audit.sqlalchemy_logger import SqlAlchemyAuditLogger
from app.infrastructure.persistence.repositories import CallSessionRepository, HotelRepository, QuoteRepository, TripRepository


def _strip_json(s: str) -> str:
    t = s.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


class SimulatedHotelOutbound:
    """Implements `HotelOutboundPort`: LLM-simulated hotel call (no external PSTN on the public Linq API surface)."""

    def __init__(self) -> None:
        pass

    def run_quote_call(
        self,
        db: Session,
        *,
        trip_id: uuid.UUID,
        hotel_id: uuid.UUID,
    ) -> tuple[CallSession, Quote]:
        trip_repo = TripRepository(db)
        hotel_repo = HotelRepository(db)
        quote_repo = QuoteRepository(db)
        call_repo = CallSessionRepository(db)
        audit = SqlAlchemyAuditLogger(db)
        call_svc = CallSessionService(db, audit)

        trip = trip_repo.get_required(trip_id)
        hotel = hotel_repo.get_required(hotel_id)

        call = call_svc.start(trip_id=trip_id, hotel_id=hotel_id, recording_enabled=False)
        call = call_repo.patch(
            call,
            status=CallStatus.in_progress,
            telephony_call_id=f"sim:{call.id}",
        )

        loyalty = ""
        if isinstance(trip.preferences, dict) and "loyalty" in trip.preferences:
            loyalty = json.dumps(trip.preferences.get("loyalty"))

        spec = _simulate_quote(trip, hotel, loyalty)
        quote = Quote(
            trip_id=trip_id,
            hotel_id=hotel_id,
            call_id=call.id,
            source="simulated_call",
            room_type=spec.get("room_type"),
            occupancy=trip.guests,
            nightly_rate=_dec(spec.get("nightly_rate")),
            taxes_fees=_dec(spec.get("taxes_fees")),
            total_price=_dec(spec.get("total_price")),
            currency=str(spec.get("currency") or trip.currency or "USD")[:8],
            included_items=spec.get("included_items") if isinstance(spec.get("included_items"), dict) else {},
            deposit={},
            cancellation=spec.get("cancellation") if isinstance(spec.get("cancellation"), dict) else {"refundable": False},
            check_in_out={},
            raw_summary=str(spec.get("raw_summary") or "Simulated quote."),
            confidence=70,
        )
        quote = quote_repo.save_new(quote)

        facts: dict[str, Any] = {
            "simulated": True,
            "member_discount_discussed": bool(spec.get("member_discount_discussed")),
            "hold_confirmation": spec.get("hold_confirmation"),
        }
        call_repo.patch(
            call,
            status=CallStatus.completed,
            extracted_facts=facts,
        )
        return call, quote


def _dec(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def _simulate_quote(trip: TripRequest, hotel: HotelCandidate, loyalty_json: str) -> dict[str, Any]:
    system = """You simulate the outcome of a phone call to a hotel front desk for a rate quote.
Return ONLY valid JSON with keys:
- nightly_rate (number), taxes_fees (number), total_price (number), currency (string)
- room_type (string)
- cancellation (object with refundable boolean)
- included_items (object)
- raw_summary (one paragraph, natural language quote recap)
- member_discount_discussed (boolean) — true if loyalty membership changed the rate narrative
- hold_confirmation (string or null) — faux confirmation / hold reference if the agent would give one without payment

Be plausible and concise."""

    user = f"""Trip: destination={trip.destination}, check_in={trip.check_in}, check_out={trip.check_out}, guests={trip.guests}, rooms={trip.rooms}.
Budget total (soft cap): {trip.budget_total}
Hotel: name={hotel.name}, phone={hotel.phone_e164}, address={hotel.address}
Trip preferences JSON: {json.dumps(trip.preferences or {})}
Trip constraints JSON: {json.dumps(trip.constraints or {})}
Chain loyalty context: {loyalty_json or 'none'}

Simulate asking for best flexible rate, taxes, whether a loyalty rate applies, and a courtesy hold without payment card."""

    raw = chat_response_text(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user[:14000]},
        ],
        temperature=0.3,
        max_tokens=2048,
    )
    try:
        return json.loads(_strip_json(raw))
    except json.JSONDecodeError:
        return {
            "nightly_rate": 199,
            "taxes_fees": 35,
            "total_price": 234,
            "currency": trip.currency or "USD",
            "room_type": "standard",
            "cancellation": {"refundable": True},
            "included_items": {},
            "raw_summary": raw[:800],
            "member_discount_discussed": False,
            "hold_confirmation": None,
        }
