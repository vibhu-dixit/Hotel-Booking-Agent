from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_trip_service
from app.api.schemas import IntentParseRequest, IntentParseResponse, TripStartRequest, TripStartResponse
from app.application.trip_service import TripService

router = APIRouter()


@router.post("/trip/start", response_model=TripStartResponse)
def trip_start(req: TripStartRequest, svc: Annotated[TripService, Depends(get_trip_service)]) -> TripStartResponse:
    result = svc.start_trip(
        user_phone_e164=req.user_phone_e164,
        destination=req.destination,
        check_in=req.check_in,
        check_out=req.check_out,
        guests=req.guests,
        rooms=req.rooms,
        budget_total=req.budget_total,
        currency=req.currency,
        locale=req.locale,
        ranking_priority=req.ranking_priority,
    )
    return TripStartResponse(trip_id=result.trip_id, user_id=result.user_id)


@router.post("/intent/parse", response_model=IntentParseResponse)
def intent_parse(req: IntentParseRequest, svc: Annotated[TripService, Depends(get_trip_service)]) -> IntentParseResponse:
    parsed = svc.parse_and_store_intent(req.trip_id, req.user_text)
    return IntentParseResponse(
        trip_id=req.trip_id,
        preferences=parsed.preferences,
        constraints=parsed.constraints,
    )
