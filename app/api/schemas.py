from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class TripStartRequest(BaseModel):
    user_phone_e164: str | None = None
    destination: str
    check_in: date
    check_out: date
    guests: int = Field(ge=1, le=20)
    rooms: int = Field(default=1, ge=1, le=10)
    budget_total: float | None = None
    currency: str = "USD"
    locale: str | None = None
    # Stored on trip.preferences — drives quote/hotel ranking (see QuoteScorer).
    ranking_priority: str | None = Field(
        default=None,
        description="lowest_price | budget_fit | highest_rating | closest | balanced",
    )


class TripStartResponse(BaseModel):
    trip_id: uuid.UUID
    user_id: uuid.UUID


class IntentParseRequest(BaseModel):
    trip_id: uuid.UUID
    user_text: str


class IntentParseResponse(BaseModel):
    trip_id: uuid.UUID
    preferences: dict
    constraints: dict


class HotelSearchRequest(BaseModel):
    trip_id: uuid.UUID


class HotelCandidateOut(BaseModel):
    id: uuid.UUID
    name: str
    address: str | None
    phone_e164: str | None
    metadata: dict
    nightly_rate: float | None = None
    taxes_fees: float | None = None
    total_price: float | None = None
    currency: str | None = None


class HotelSearchResponse(BaseModel):
    trip_id: uuid.UUID
    hotels: list[HotelCandidateOut]


class CallStartRequest(BaseModel):
    trip_id: uuid.UUID
    hotel_id: uuid.UUID
    recording_enabled: bool = False


class CallStartResponse(BaseModel):
    call_id: uuid.UUID
    status: str


class CallStatusResponse(BaseModel):
    call_id: uuid.UUID
    status: str
    extracted_facts: dict


class DecisionEvaluateRequest(BaseModel):
    trip_id: uuid.UUID


class DecisionEvaluateResponse(BaseModel):
    decision_id: uuid.UUID
    ranked: list[dict]


class BookingApproveRequest(BaseModel):
    user_id: uuid.UUID
    trip_id: uuid.UUID
    quote_id: uuid.UUID
    approval_text_version: str = "v1"
    approval_payload: dict = Field(default_factory=dict)


class BookingApproveResponse(BaseModel):
    approval_id: uuid.UUID
    approved_at: datetime


class BookingCreateRequest(BaseModel):
    user_id: uuid.UUID
    trip_id: uuid.UUID
    quote_id: uuid.UUID

    # Optional reservation details (kept minimal; avoid collecting payment cards here)
    guest_name: str | None = None
    guest_email: str | None = None


class BookingCreateResponse(BaseModel):
    booking_id: uuid.UUID
    status: str


class BookingGetResponse(BaseModel):
    booking_id: uuid.UUID
    status: str
    confirmation_number: str | None
    final_terms: dict


class AiTtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class AiTranscribeResponse(BaseModel):
    text: str


class AiChatMessage(BaseModel):
    role: str
    content: str


class AiChatRequest(BaseModel):
    messages: list[AiChatMessage] = Field(min_length=1)
    stream: bool = False
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    top_p: float = Field(default=0.95, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, ge=1, le=32768)


class AiChatResponse(BaseModel):
    text: str


class PaymentLinkResponse(BaseModel):
    url: str

