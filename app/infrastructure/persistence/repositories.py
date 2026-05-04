from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    BookingApproval,
    BookingRecord,
    CallSession,
    DecisionResult,
    HotelCandidate,
    LinqWebhookDedup,
    MessagingSession,
    Quote,
    TripRequest,
    User,
)


class UserRepository:
    def __init__(self, db: Session):
        self._db = db

    def get_by_phone_e164(self, phone_e164: str) -> User | None:
        # Phone should be unique; if legacy duplicates exist, pick one so Linq webhooks don't 500.
        return (
            self._db.execute(select(User).where(User.phone_e164 == phone_e164).limit(1)).scalars().first()
        )

    def get_or_create_by_phone_e164(self, phone_e164: str) -> User:
        existing = self.get_by_phone_e164(phone_e164)
        if existing:
            return existing
        return self.create(phone_e164=phone_e164)

    def create(self, *, phone_e164: str | None) -> User:
        user = User(phone_e164=phone_e164)
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return user


class TripRepository:
    def __init__(self, db: Session):
        self._db = db

    def create(
        self,
        *,
        user_id: uuid.UUID,
        destination: str,
        check_in,
        check_out,
        guests: int,
        rooms: int,
        budget_total,
        currency: str,
        locale: str | None,
    ) -> TripRequest:
        trip = TripRequest(
            user_id=user_id,
            destination=destination,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            rooms=rooms,
            budget_total=budget_total,
            currency=currency,
            locale=locale,
            preferences={},
            constraints={},
        )
        self._db.add(trip)
        self._db.commit()
        self._db.refresh(trip)
        return trip

    def get_required(self, trip_id: uuid.UUID) -> TripRequest:
        return self._db.execute(select(TripRequest).where(TripRequest.id == trip_id)).scalar_one()

    def save_preferences(self, trip: TripRequest, *, preferences: dict, constraints: dict) -> None:
        trip.preferences = preferences
        trip.constraints = constraints
        self._db.commit()

    def merge_preferences(self, trip: TripRequest, *, preferences: dict, constraints: dict) -> None:
        merged_p = {**dict(trip.preferences or {}), **preferences}
        merged_c = {**dict(trip.constraints or {}), **constraints}
        trip.preferences = merged_p
        trip.constraints = merged_c
        self._db.commit()

    def update_trip_core(
        self,
        trip: TripRequest,
        *,
        destination: str | None = None,
        check_in=None,
        check_out=None,
        guests: int | None = None,
        rooms: int | None = None,
        budget_total=None,
        currency: str | None = None,
    ) -> None:
        if destination is not None:
            trip.destination = destination
        if check_in is not None:
            trip.check_in = check_in
        if check_out is not None:
            trip.check_out = check_out
        if guests is not None:
            trip.guests = guests
        if rooms is not None:
            trip.rooms = rooms
        if budget_total is not None:
            trip.budget_total = budget_total
        if currency is not None:
            trip.currency = currency
        self._db.commit()


class HotelRepository:
    def __init__(self, db: Session):
        self._db = db

    def get_required(self, hotel_id: uuid.UUID) -> HotelCandidate:
        return self._db.execute(select(HotelCandidate).where(HotelCandidate.id == hotel_id)).scalar_one()

    def list_for_trip(self, trip_id: uuid.UUID) -> list[HotelCandidate]:
        return list(self._db.execute(select(HotelCandidate).where(HotelCandidate.trip_id == trip_id)).scalars().all())

    def add_hotels(self, hotels: list[HotelCandidate]) -> None:
        self._db.add_all(hotels)
        self._db.commit()
        for h in hotels:
            self._db.refresh(h)


class QuoteRepository:
    def __init__(self, db: Session):
        self._db = db

    def list_for_trip(self, trip_id: uuid.UUID) -> list[Quote]:
        return list(self._db.execute(select(Quote).where(Quote.trip_id == trip_id)).scalars().all())

    def get_required_for_trip(self, trip_id: uuid.UUID, quote_id: uuid.UUID) -> Quote:
        return self._db.execute(select(Quote).where(Quote.id == quote_id, Quote.trip_id == trip_id)).scalar_one()

    def exists_for_pair(self, trip_id: uuid.UUID, hotel_id: uuid.UUID) -> bool:
        row = self._db.execute(
            select(Quote.id).where(Quote.trip_id == trip_id, Quote.hotel_id == hotel_id).limit(1)
        ).scalar_one_or_none()
        return row is not None

    def add(self, quote: Quote) -> None:
        self._db.add(quote)

    def commit(self) -> None:
        self._db.commit()

    def save_new(self, quote: Quote) -> Quote:
        self._db.add(quote)
        self._db.commit()
        self._db.refresh(quote)
        return quote


class CallSessionRepository:
    def __init__(self, db: Session):
        self._db = db

    def save(self, call: CallSession) -> CallSession:
        self._db.add(call)
        self._db.commit()
        self._db.refresh(call)
        return call

    def get_required(self, call_id: uuid.UUID) -> CallSession:
        return self._db.execute(select(CallSession).where(CallSession.id == call_id)).scalar_one()

    def patch(self, call: CallSession, **fields: object) -> CallSession:
        for k, v in fields.items():
            setattr(call, k, v)
        call.updated_at = datetime.utcnow()
        self._db.commit()
        self._db.refresh(call)
        return call


class DecisionRepository:
    def __init__(self, db: Session):
        self._db = db

    def save(self, decision: DecisionResult) -> DecisionResult:
        self._db.add(decision)
        self._db.commit()
        self._db.refresh(decision)
        return decision


class BookingApprovalRepository:
    def __init__(self, db: Session):
        self._db = db

    def find_by_user_trip_quote(
        self, *, user_id: uuid.UUID, trip_id: uuid.UUID, quote_id: uuid.UUID
    ) -> BookingApproval | None:
        return self._db.execute(
            select(BookingApproval).where(
                BookingApproval.user_id == user_id,
                BookingApproval.trip_id == trip_id,
                BookingApproval.quote_id == quote_id,
            )
        ).scalar_one_or_none()

    def save(self, approval: BookingApproval) -> BookingApproval:
        self._db.add(approval)
        self._db.commit()
        self._db.refresh(approval)
        return approval


class BookingRecordRepository:
    def __init__(self, db: Session):
        self._db = db

    def save(self, booking: BookingRecord) -> BookingRecord:
        self._db.add(booking)
        self._db.commit()
        self._db.refresh(booking)
        return booking

    def get_required(self, booking_id: uuid.UUID) -> BookingRecord:
        return self._db.execute(select(BookingRecord).where(BookingRecord.id == booking_id)).scalar_one()

    def patch(self, booking: BookingRecord, **fields: object) -> BookingRecord:
        for k, v in fields.items():
            setattr(booking, k, v)
        booking.updated_at = datetime.utcnow()
        self._db.commit()
        self._db.refresh(booking)
        return booking


class MessagingSessionRepository:
    def __init__(self, db: Session):
        self._db = db

    def get_by_chat_id(self, linq_chat_id: str) -> MessagingSession | None:
        return self._db.execute(
            select(MessagingSession).where(MessagingSession.linq_chat_id == linq_chat_id)
        ).scalar_one_or_none()

    def create(self, *, user_id: uuid.UUID, linq_chat_id: str, phase: str = "collecting_intent") -> MessagingSession:
        row = MessagingSession(
            user_id=user_id,
            trip_id=None,
            linq_chat_id=linq_chat_id,
            phase=phase,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def get_or_create(self, *, user_id: uuid.UUID, linq_chat_id: str) -> MessagingSession:
        ex = self.get_by_chat_id(linq_chat_id)
        if ex:
            return ex
        return self.create(user_id=user_id, linq_chat_id=linq_chat_id)

    def save(self, row: MessagingSession) -> MessagingSession:
        row.updated_at = datetime.utcnow()
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row


class LinqWebhookDedupRepository:
    def __init__(self, db: Session):
        self._db = db

    def try_acquire(self, event_id: str) -> bool:
        row = LinqWebhookDedup(event_id=event_id)
        self._db.add(row)
        try:
            self._db.commit()
            return True
        except IntegrityError:
            self._db.rollback()
            return False
