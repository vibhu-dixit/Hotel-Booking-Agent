from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import NoResultFound

from app.api.deps import DbSession
from app.api.schemas import PaymentLinkResponse
from app.application.messaging.booking_com_links import build_booking_com_payment_url
from app.infrastructure.persistence.repositories import HotelRepository

router = APIRouter()


@router.get("/trip/{trip_id}/payment-link", response_model=PaymentLinkResponse)
def trip_payment_link(
    trip_id: uuid.UUID,
    db: DbSession,
    hotel_id: uuid.UUID = Query(..., description="Hotel candidate id from search results"),
    user_id: uuid.UUID | None = Query(None),
) -> PaymentLinkResponse:
    """Returns a Booking.com search URL with dates, guests, and selected hotel name prefilled."""
    hr = HotelRepository(db)
    try:
        h = hr.get_required(hotel_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="hotel not found") from None
    if h.trip_id != trip_id:
        raise HTTPException(status_code=404, detail="hotel does not belong to this trip")

    _ = user_id  # reserved for future affiliate / tracking
    url = build_booking_com_payment_url(db, trip_id=trip_id, hotel_id=hotel_id)
    return PaymentLinkResponse(url=url)
