from __future__ import annotations

import logging
import uuid
from decimal import Decimal

import httpx
from sqlalchemy.orm import Session

from app.application.scoring.quote_scorer import QuoteScorer
from app.core.config import settings
from app.db.models import HotelCandidate, Quote, TripRequest
from app.domain.exceptions import HotelDiscoveryFailed
from app.infrastructure.maps import google_hotels
from app.infrastructure.maps.google_hotels import google_api_error_detail
from app.infrastructure.persistence.repositories import HotelRepository, QuoteRepository, TripRepository

logger = logging.getLogger(__name__)


class HotelDiscoveryService:
    """
    Hotel search + stub quote seeding.
    Swap `search` implementation for a real provider while keeping quote normalization here.
    """

    _STUB_RATES: tuple[Decimal, ...] = (Decimal("189.00"), Decimal("215.50"))
    _STUB_TAXES = Decimal("28.00")

    def __init__(self, db: Session):
        self._trips = TripRepository(db)
        self._hotels = HotelRepository(db)
        self._quotes = QuoteRepository(db)

    def search(self, trip_id: uuid.UUID) -> list[HotelCandidate]:
        trip = self._trips.get_required(trip_id)
        existing = self._hotels.list_for_trip(trip_id)
        if existing:
            limited = self._limit_hotels(existing)
            self._ensure_stub_quotes(trip_id=trip_id, trip_currency=trip.currency or "USD", hotels=limited)
            return self._rank_hotels(trip, limited)

        if google_hotels.google_hotels_enabled():
            key = settings.google_maps_api_key or ""
            try:
                discovered = google_hotels.build_hotels_for_trip(trip, api_key=key)
            except httpx.HTTPStatusError as e:
                gmsg = google_api_error_detail(e.response)
                detail = f"Google Places/Maps request failed (HTTP {e.response.status_code})."
                if gmsg:
                    detail += f" Google says: {gmsg}"
                if e.response.status_code == 403:
                    detail += (
                        " — For server-side Places Text Search, enable Places API (New) on the same project "
                        "(the Maps JavaScript API alone is not enough), link billing, and under Credentials ensure "
                        "this key’s API restrictions include Places API (New), or use no API restriction for local dev."
                    )
                else:
                    detail += " Confirm Geocoding API and Places API (New) are enabled for this API key."
                logger.warning("google hotel discovery HTTP error: %s", detail)
                raise HotelDiscoveryFailed(detail) from e
            except Exception as e:
                logger.exception("google hotel discovery failed")
                raise HotelDiscoveryFailed(
                    "Hotel discovery failed. Try a more specific destination (e.g. 'Page, AZ'). "
                    "Check server logs if this persists."
                ) from e
            if not discovered:
                raise HotelDiscoveryFailed(
                    "No lodging results from Google for this destination. Try a more specific place "
                    "(e.g. 'Page, AZ' instead of 'Page').",
                    status_code=404,
                )
            self._hotels.add_hotels(discovered)
            self._ensure_stub_quotes(trip_id=trip_id, trip_currency=trip.currency or "USD", hotels=discovered)
            ranked = self._rank_hotels(trip, self._hotels.list_for_trip(trip_id))
            return ranked

        seeded = [
            HotelCandidate(
                trip_id=trip_id,
                place_id=None,
                provider_ids={},
                name=f"{trip.destination} Central Hotel",
                address=None,
                phone_e164=None,
                extra_metadata={"seeded": True, "rating": 4.3},
            ),
            HotelCandidate(
                trip_id=trip_id,
                place_id=None,
                provider_ids={},
                name=f"{trip.destination} Riverside Inn",
                address=None,
                phone_e164=None,
                extra_metadata={"seeded": True, "rating": 4.1},
            ),
            HotelCandidate(
                trip_id=trip_id,
                place_id=None,
                provider_ids={},
                name=f"{trip.destination} Airport Suites",
                address=None,
                phone_e164=None,
                extra_metadata={"seeded": True, "rating": 4.0},
            ),
            HotelCandidate(
                trip_id=trip_id,
                place_id=None,
                provider_ids={},
                name=f"{trip.destination} Downtown Lodge",
                address=None,
                phone_e164=None,
                extra_metadata={"seeded": True, "rating": 3.9},
            ),
        ]
        seeded = self._limit_hotels(seeded)
        self._hotels.add_hotels(seeded)
        self._ensure_stub_quotes(trip_id=trip_id, trip_currency=trip.currency or "USD", hotels=seeded)
        ranked = self._rank_hotels(trip, self._hotels.list_for_trip(trip_id))
        return ranked

    def _rank_hotels(self, trip: TripRequest, hotels: list[HotelCandidate]) -> list[HotelCandidate]:
        """Order hotels by QuoteScorer so list matches trip.preferences[\"ranking_priority\"]."""
        if not hotels:
            return hotels
        quotes = self._quotes.list_for_trip(trip.id)
        by_hotel = {q.hotel_id: q for q in quotes}
        scorer = QuoteScorer()
        scored: list[tuple[float, HotelCandidate]] = []
        for h in hotels:
            q = by_hotel.get(h.id)
            if q is None:
                scored.append((float("-inf"), h))
                continue
            s, _ = scorer.score(trip, h, q)
            scored.append((s, h))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [h for _, h in scored]

    def _limit_hotels(self, hotels: list[HotelCandidate]) -> list[HotelCandidate]:
        n = max(1, int(settings.hotel_search_max_results))
        return hotels[:n]

    def _ensure_stub_quotes(
        self, *, trip_id: uuid.UUID, trip_currency: str, hotels: list[HotelCandidate]
    ) -> None:
        for idx, hotel in enumerate(hotels):
            if self._quotes.exists_for_pair(trip_id, hotel.id):
                continue
            nightly = self._STUB_RATES[idx % len(self._STUB_RATES)]
            total = nightly + self._STUB_TAXES
            self._quotes.add(
                Quote(
                    trip_id=trip_id,
                    hotel_id=hotel.id,
                    call_id=None,
                    source="stub",
                    nightly_rate=nightly,
                    taxes_fees=self._STUB_TAXES,
                    total_price=total,
                    currency=trip_currency,
                    cancellation={"refundable": idx == 0},
                    raw_summary="Stub quote for demo UI.",
                )
            )
        self._quotes.commit()
