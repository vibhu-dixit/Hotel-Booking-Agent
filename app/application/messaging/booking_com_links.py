from __future__ import annotations

import uuid
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import HotelCandidate, TripRequest
from app.infrastructure.persistence.repositories import HotelRepository, TripRepository

BOOKING_COM_SEARCH_BASE = "https://www.booking.com/searchresults.html"


def build_booking_com_search_url(*, trip: TripRequest, hotel: HotelCandidate) -> str:
    """
    Deep link to Booking.com search results with dates and guest counts prefilled.

    Users complete selection and payment on Booking.com (there is no single static
    “payment URL” per hotel without Booking’s partner APIs).
    """
    dest = (trip.destination or "").strip()
    name = (hotel.name or "").strip()
    ss = f"{name} {dest}".strip() if name else dest
    if not ss:
        ss = dest or name or "hotel"

    params: dict[str, str] = {
        "ss": ss,
        "checkin": trip.check_in.isoformat(),
        "checkout": trip.check_out.isoformat(),
        "group_adults": str(max(1, trip.guests)),
        "no_rooms": str(max(1, trip.rooms)),
    }

    aid = (settings.booking_com_affiliate_id or "").strip()
    if aid:
        params["aid"] = aid

    return f"{BOOKING_COM_SEARCH_BASE}?{urlencode(params)}"


def build_booking_com_payment_url(db: Session, *, trip_id: uuid.UUID, hotel_id: uuid.UUID) -> str:
    trips = TripRepository(db)
    hr = HotelRepository(db)
    trip = trips.get_required(trip_id)
    hotel = hr.get_required(hotel_id)
    return build_booking_com_search_url(trip=trip, hotel=hotel)
