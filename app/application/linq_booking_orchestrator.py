from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.application.hotel_discovery_service import HotelDiscoveryService
from app.application.intent.llm_trip_extraction import extract_trip_spec
from app.application.messaging import merge_reference_location_into_trip, upsert_trip_from_extracted_spec
from app.application.messaging.hotel_lookup import hotel_names_by_id
from app.application.messaging.booking_com_links import build_booking_com_payment_url
from app.application.messaging.user_copy import (
    FOOTER_PICK,
    HEADER_OPTIONS,
    REPLY_DESTINATION,
    REPLY_EMPTY,
    REPLY_LEGACY_SESSION_RESET,
    REPLY_NEED_DATES,
    REPLY_NEED_NVIDIA,
    REPLY_NO_HOTELS,
    REPLY_PARSE_ERROR,
    REPLY_RESET,
    REPLY_THREAD_CLOSED,
    RETRY_PICK_HEADER,
    format_hotel_option_lines,
    format_payment_link_message,
)
from app.db.models import HotelCandidate, MessagingSession, User
from app.domain.exceptions import HotelDiscoveryFailed
from app.domain.messaging import MessagingWorkflowPhase, resolve_hotel_choice_by_name
from app.domain.ports import ChannelMessagingPort
from app.infrastructure.persistence.repositories import (
    HotelRepository,
    MessagingSessionRepository,
    QuoteRepository,
    TripRepository,
    UserRepository,
)
from app.infrastructure.telephony.linq_messaging_adapter import LinqChannelMessagingAdapter
from app.infrastructure.telephony.linq_payloads import NormalizedInboundMessage

logger = logging.getLogger(__name__)

_INTENT_LINES_KEY = "intent_message_lines"


def _starts_new_booking_after_completed(text: str) -> bool:
    """True if we should leave `completed` and accept a new itinerary (same iMessage thread).

    Without this, only phrases like \"new trip\" worked — greetings such as \"hi\" triggered
    REPLY_THREAD_CLOSED even though users expect to continue the conversation.
    """
    t = text.lower().strip()
    if t in frozenset({"hi", "hello", "hey", "yo", "hiya", "howdy", "sup"}):
        return True
    phrases = (
        "new trip",
        "start over",
        "restart",
        "book again",
        "another trip",
        "book a trip",
        "start booking",
    )
    if any(t == p or t.startswith(p + " ") for p in phrases):
        return True
    # User pasted a full trip again after finishing — reset instead of \"thread closed\".
    markers = (
        "check-in",
        "check in",
        "check-out",
        "check out",
        "checkout",
        "guest",
        "night",
        "room",
    )
    if len(t) >= 20 and sum(1 for m in markers if m in t) >= 2:
        return True
    return False


def _phase(ms: MessagingSession) -> str:
    return str(ms.phase)


class LinqBookingOrchestrator:
    """
    Linq SMS/iMessage flow (text-only): LLM extracts trip → hotel search → user picks hotel → payment link.
    Voice transcription and outbound hotel calls are disabled for now.
    """

    def __init__(
        self,
        *,
        messaging: ChannelMessagingPort | None = None,
    ) -> None:
        self._messaging = messaging or LinqChannelMessagingAdapter()

    def handle_inbound(self, db: Session, norm: NormalizedInboundMessage) -> None:
        users = UserRepository(db)
        ms_repo = MessagingSessionRepository(db)

        user = users.get_or_create_by_phone_e164(norm.from_e164)
        if not user.phone_e164:
            user.phone_e164 = norm.from_e164
            db.commit()

        ms = ms_repo.get_or_create(user_id=user.id, linq_chat_id=norm.chat_id)

        body = self._compose_user_text(norm)
        if not body.strip():
            self._messaging.send_text(norm.from_e164, REPLY_EMPTY)
            return

        text = body.strip()
        ph = _phase(ms)

        if ph == MessagingWorkflowPhase.completed.value:
            if _starts_new_booking_after_completed(text):
                ms.phase = MessagingWorkflowPhase.collecting_intent.value
                ms.trip_id = None
                ms.selected_hotel_id = None
                ms.selected_quote_id = None
                ms.extra = {}
                ms_repo.save(ms)
                ph = _phase(ms)
            else:
                self._messaging.send_text(norm.from_e164, REPLY_THREAD_CLOSED)
                return

        if ph in (
            MessagingWorkflowPhase.awaiting_quote_approval.value,
            MessagingWorkflowPhase.calling_hotels.value,
        ):
            ms.phase = MessagingWorkflowPhase.collecting_intent.value
            ms_repo.save(ms)
            self._messaging.send_text(norm.from_e164, REPLY_LEGACY_SESSION_RESET)
            return

        if ph == MessagingWorkflowPhase.awaiting_hotel_pick.value:
            self._handle_hotel_pick(db, ms, user, text, ms_repo)
            return

        self._collect_and_search(db, ms, user, text, ms_repo)

    def _compose_user_text(self, norm: NormalizedInboundMessage) -> str:
        # Voice / media transcription intentionally disabled — text-only channel for now.
        # norm.media_urls ignored.
        return (norm.text or "").strip()

    def _build_hotel_rows(
        self,
        db: Session,
        trip_id: uuid.UUID,
        hotels: list[HotelCandidate],
    ) -> list[tuple[str, object | None, str | None, str | None]]:
        quotes = QuoteRepository(db).list_for_trip(trip_id)
        by_hotel = {q.hotel_id: q for q in quotes}
        rows: list[tuple[str, object | None, str | None, str | None]] = []
        for h in hotels:
            km = h.extra_metadata.get("distance_km") if h.extra_metadata else None
            q = by_hotel.get(h.id)
            price = None
            if q is not None and q.total_price is not None:
                cur = q.currency or "USD"
                price = f"{cur} {float(q.total_price):.2f} total"
                if q.nightly_rate is not None:
                    price += f", {float(q.nightly_rate):.2f}/night"
            maps_uri = None
            if isinstance(h.extra_metadata, dict):
                mu = h.extra_metadata.get("maps_uri")
                if isinstance(mu, str) and mu.strip():
                    maps_uri = mu
            rows.append((h.name, km, price, maps_uri))
        return rows

    def _handle_hotel_pick(
        self,
        db: Session,
        ms: MessagingSession,
        user: User,
        text: str,
        ms_repo: MessagingSessionRepository,
    ) -> None:
        ids = list(ms.extra.get("hotel_ids") or [])
        if not ids or not ms.trip_id:
            ms.phase = MessagingWorkflowPhase.collecting_intent.value
            ms_repo.save(ms)
            self._messaging.send_text(user.phone_e164 or "", REPLY_RESET)
            return

        names = hotel_names_by_id(db, ids)
        picked = resolve_hotel_choice_by_name(text, ids, name_for_id=names)

        if picked is None:
            trip_id = ms.trip_id
            assert trip_id is not None
            by_id = {str(h.id): h for h in HotelRepository(db).list_for_trip(trip_id)}
            ordered = [by_id[hid] for hid in ids if hid in by_id]
            rows = self._build_hotel_rows(db, trip_id, ordered)
            block = format_hotel_option_lines(rows)
            self._messaging.send_text(
                user.phone_e164 or "",
                f"{RETRY_PICK_HEADER}\n\n{HEADER_OPTIONS}\n{block}\n\n{FOOTER_PICK}",
            )
            return

        ms.selected_hotel_id = picked
        trip_id = ms.trip_id
        assert trip_id is not None

        url = build_booking_com_payment_url(db, trip_id=trip_id, hotel_id=picked)
        ms.phase = MessagingWorkflowPhase.completed.value
        ms.extra = {
            **dict(ms.extra or {}),
            "payment_url": url or None,
            "selected_hotel_id": str(picked),
        }
        ms_repo.save(ms)

        self._messaging.send_text(user.phone_e164 or "", format_payment_link_message(url))

    def _collect_and_search(
        self,
        db: Session,
        ms: MessagingSession,
        user: User,
        text: str,
        ms_repo: MessagingSessionRepository,
    ) -> None:
        raw_lines = ms.extra.get(_INTENT_LINES_KEY)
        lines: list[str] = list(raw_lines) if isinstance(raw_lines, list) else []
        lines.append(text)
        combined = "\n".join(lines)

        try:
            spec = extract_trip_spec(combined, fill_default_dates=False)
        except RuntimeError:
            self._messaging.send_text(user.phone_e164 or "", REPLY_NEED_NVIDIA)
            return
        except Exception as e:  # noqa: BLE001
            logger.exception("intent extraction failed")
            self._messaging.send_text(user.phone_e164 or "", REPLY_PARSE_ERROR.format(detail=e))
            return

        if not spec.destination:
            ms.extra = {**dict(ms.extra or {}), _INTENT_LINES_KEY: lines}
            ms_repo.save(ms)
            self._messaging.send_text(user.phone_e164 or "", REPLY_DESTINATION)
            return

        if spec.check_in is None or spec.check_out is None:
            ms.extra = {**dict(ms.extra or {}), _INTENT_LINES_KEY: lines}
            ms_repo.save(ms)
            self._messaging.send_text(user.phone_e164 or "", REPLY_NEED_DATES)
            return

        trips = TripRepository(db)
        upsert_trip_from_extracted_spec(trips, ms=ms, user=user, spec=spec)
        trip = trips.get_required(ms.trip_id)  # type: ignore[arg-type]
        merge_reference_location_into_trip(trips, trip, spec)

        try:
            hotels = HotelDiscoveryService(db).search(trip.id)
        except HotelDiscoveryFailed as e:
            self._messaging.send_text(user.phone_e164 or "", str(e)[:900])
            return
        if not hotels:
            self._messaging.send_text(user.phone_e164 or "", REPLY_NO_HOTELS)
            return

        ex = {**dict(ms.extra or {})}
        ex.pop(_INTENT_LINES_KEY, None)
        ex["hotel_ids"] = [str(h.id) for h in hotels]
        ms.extra = ex
        ms.phase = MessagingWorkflowPhase.awaiting_hotel_pick.value
        ms_repo.save(ms)

        rows = self._build_hotel_rows(db, trip.id, hotels)
        block = format_hotel_option_lines(rows)
        self._messaging.send_text(
            user.phone_e164 or "",
            f"{HEADER_OPTIONS}\n{block}\n{FOOTER_PICK}",
        )
