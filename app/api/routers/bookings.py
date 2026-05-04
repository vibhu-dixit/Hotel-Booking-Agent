from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_booking_workflow
from app.api.schemas import (
    BookingApproveRequest,
    BookingApproveResponse,
    BookingCreateRequest,
    BookingCreateResponse,
    BookingGetResponse,
)
from app.application.booking_service import BookingWorkflowService

router = APIRouter()


@router.post("/booking/approve", response_model=BookingApproveResponse)
def booking_approve(
    req: BookingApproveRequest,
    svc: Annotated[BookingWorkflowService, Depends(get_booking_workflow)],
) -> BookingApproveResponse:
    approval = svc.record_approval(
        user_id=req.user_id,
        trip_id=req.trip_id,
        quote_id=req.quote_id,
        approval_text_version=req.approval_text_version,
        approval_payload=req.approval_payload,
    )
    return BookingApproveResponse(approval_id=approval.id, approved_at=approval.approved_at)


@router.post("/booking/create", response_model=BookingCreateResponse)
def booking_create(
    req: BookingCreateRequest,
    svc: Annotated[BookingWorkflowService, Depends(get_booking_workflow)],
) -> BookingCreateResponse:
    booking = svc.create_booking(user_id=req.user_id, trip_id=req.trip_id, quote_id=req.quote_id)
    return BookingCreateResponse(booking_id=booking.id, status=booking.status.value)


@router.get("/booking/{booking_id}", response_model=BookingGetResponse)
def booking_get(
    booking_id: uuid.UUID,
    svc: Annotated[BookingWorkflowService, Depends(get_booking_workflow)],
) -> BookingGetResponse:
    booking = svc.get_booking(booking_id)
    return BookingGetResponse(
        booking_id=booking.id,
        status=booking.status.value,
        confirmation_number=booking.confirmation_number,
        final_terms=booking.final_terms,
    )
