from __future__ import annotations

from app.application.intent.llm_trip_extraction import ExtractedTripSpec
from app.db.models import MessagingSession, TripRequest, User
from app.infrastructure.persistence.repositories import TripRepository


def upsert_trip_from_extracted_spec(
    trips: TripRepository,
    *,
    ms: MessagingSession,
    user: User,
    spec: ExtractedTripSpec,
) -> TripRequest:
    """Create or update TripRequest from LLM extraction; sets ms.trip_id when creating."""
    assert spec.check_in is not None and spec.check_out is not None and spec.destination

    if ms.trip_id:
        trip = trips.get_required(ms.trip_id)
        trips.update_trip_core(
            trip,
            destination=spec.destination,
            check_in=spec.check_in,
            check_out=spec.check_out,
            guests=spec.guests,
            rooms=spec.rooms,
            budget_total=spec.budget_total,
            currency=spec.currency,
        )
        trips.merge_preferences(trip, preferences=spec.preferences, constraints=spec.constraints)
        return trip

    trip = trips.create(
        user_id=user.id,
        destination=spec.destination,
        check_in=spec.check_in,
        check_out=spec.check_out,
        guests=spec.guests,
        rooms=spec.rooms,
        budget_total=spec.budget_total,
        currency=spec.currency,
        locale=None,
    )
    trips.merge_preferences(trip, preferences=spec.preferences, constraints=spec.constraints)
    ms.trip_id = trip.id
    return trip
