from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DbSession, get_hotel_discovery
from app.api.mappers import hotel_candidate_to_dict
from app.api.schemas import HotelSearchRequest, HotelSearchResponse
from app.application.hotel_discovery_service import HotelDiscoveryService
from app.infrastructure.persistence.repositories import QuoteRepository

router = APIRouter()


@router.post("/hotels/search", response_model=HotelSearchResponse)
def hotels_search(
    req: HotelSearchRequest,
    svc: Annotated[HotelDiscoveryService, Depends(get_hotel_discovery)],
    db: DbSession,
) -> HotelSearchResponse:
    hotels = svc.search(req.trip_id)
    quotes = QuoteRepository(db).list_for_trip(req.trip_id)
    by_hotel = {q.hotel_id: q for q in quotes}
    return HotelSearchResponse(
        trip_id=req.trip_id,
        hotels=[hotel_candidate_to_dict(h, quote=by_hotel.get(h.id)) for h in hotels],
    )
