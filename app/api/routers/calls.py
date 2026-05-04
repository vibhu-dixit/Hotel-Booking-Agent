from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_call_session_service
from app.api.schemas import CallStartRequest, CallStartResponse, CallStatusResponse
from app.application.call_session_service import CallSessionService

router = APIRouter()


@router.post("/calls/start", response_model=CallStartResponse)
def calls_start(
    req: CallStartRequest,
    svc: Annotated[CallSessionService, Depends(get_call_session_service)],
) -> CallStartResponse:
    call = svc.start(trip_id=req.trip_id, hotel_id=req.hotel_id, recording_enabled=req.recording_enabled)
    return CallStartResponse(call_id=call.id, status=call.status.value)


@router.get("/calls/{call_id}", response_model=CallStatusResponse)
def calls_get(
    call_id: uuid.UUID,
    svc: Annotated[CallSessionService, Depends(get_call_session_service)],
) -> CallStatusResponse:
    call = svc.get_status(call_id)
    return CallStatusResponse(call_id=call.id, status=call.status.value, extracted_facts=call.extracted_facts)
