from __future__ import annotations

from app.application.intent.llm_trip_extraction import ExtractedTripSpec
from app.core.config import settings
from app.db.models import TripRequest
from app.infrastructure.maps.google_hotels import geocode_address
from app.infrastructure.persistence.repositories import TripRepository


def merge_reference_location_into_trip(
    trips: TripRepository,
    trip: TripRequest,
    spec: ExtractedTripSpec,
) -> None:
    """When Google Maps is configured, persist reference point for distance-ranked results."""
    ref = spec.reference_location or (
        trip.preferences.get("reference_location") if isinstance(trip.preferences, dict) else None
    )
    if not ref or not settings.google_maps_api_key:
        return
    g = geocode_address(str(ref).strip(), api_key=settings.google_maps_api_key)
    if not g:
        return
    trips.merge_preferences(
        trip,
        preferences={"reference_location": str(ref)},
        constraints={
            "reference_lat": g[0],
            "reference_lng": g[1],
            "reference_label": str(ref),
        },
    )
