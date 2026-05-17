from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.application.hotel_discovery_service import HotelDiscoveryService
from app.application.intent.llm_trip_extraction import extract_trip_spec
from app.application.messaging import merge_reference_location_into_trip, upsert_trip_from_extracted_spec
from app.application.messaging.booking_com_links import build_booking_com_payment_url
from app.application.messaging.hotel_lookup import hotel_names_by_id
from app.application.messaging.user_copy import (
    FOOTER_PICK,
    HEADER_OPTIONS,
    REPLY_AUDIO_NO_TRANSCRIBER,
    REPLY_DESTINATION,
    REPLY_EMPTY,
    REPLY_LEGACY_SESSION_RESET,
    REPLY_NEED_DATES,
    REPLY_NEED_NVIDIA,
    REPLY_NO_HOTELS,
    REPLY_PARSE_ERROR,
    REPLY_RESET,
    REPLY_THREAD_CLOSED,
    REPLY_TRANSCRIBE_FAILED,
    RETRY_PICK_HEADER,
    format_hotel_option_lines,
    format_payment_link_message,
    hotel_sms_rows,
)
from app.core.config import settings
from app.db.models import HotelCandidate, MessagingSession, User
from app.domain.exceptions import HotelDiscoveryFailed
from app.domain.messaging import MessagingWorkflowPhase, resolve_hotel_choice_by_name
from app.infrastructure.ai.deepgram_speech import DeepgramSpeechTranscriptionAdapter
from app.infrastructure.ai.hf_speech_transcription import HuggingFaceSpeechTranscriptionAdapter
from app.infrastructure.ai.huggingface_speech import speech_gateway
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
_RESET_PHRASES = frozenset(
    {"new trip", "start over", "restart", "book again", "another trip", "start booking"}
)


@dataclass(frozen=True)
class _OutboundCtx:
    phone: str
    chat_id: str
    preferred_service: str | None = None


def _speech_backend():
    if settings.deepgram_api_key:
        return DeepgramSpeechTranscriptionAdapter()
    if speech_gateway().available:
        return HuggingFaceSpeechTranscriptionAdapter()
    return None


def _body_from_message(norm: NormalizedInboundMessage) -> str | None:
    """Text + voice note transcripts. Returns None if we should reply with an error string separately."""
    parts: list[str] = []
    if norm.text.strip():
        parts.append(norm.text.strip())

    if norm.media_urls:
        speech = _speech_backend()
        if not speech:
            return None  # caller sends REPLY_AUDIO_NO_TRANSCRIBER
        for url in norm.media_urls:
            t = speech.transcribe_media_url(url)
            if t.strip():
                parts.append(t.strip())
        if not parts:
            return None  # caller sends REPLY_TRANSCRIBE_FAILED

    return "\n".join(parts).strip()


def _is_short_reset_phrase(text: str) -> bool:
    return text.lower().strip() in _RESET_PHRASES


def _wants_new_trip_after_done(text: str) -> bool:
    t = text.lower().strip()
    if t in {"hi", "hello", "hey", "yo", "hiya", "howdy", "sup"}:
        return True
    for p in ("new trip", "start over", "restart", "book again", "another trip", "book a trip", "start booking"):
        if t == p or t.startswith(p + " "):
            return True
    markers = ("check-in", "check in", "check-out", "check out", "checkout", "guest", "night", "room")
    if len(t) >= 20 and sum(1 for m in markers if m in t) >= 2:
        return True
    return False


class LinqBookingOrchestrator:
    # SMS / iMessage: LLM trip parse → hotel search → pick by number → Booking.com link

    def __init__(self, messaging=None):
        self._sms = messaging or LinqChannelMessagingAdapter()

    def _reply(self, ctx: _OutboundCtx, text: str) -> None:
        self._sms.send_text(
            ctx.phone,
            text,
            chat_id=ctx.chat_id,
            preferred_service=ctx.preferred_service,
        )

    def handle_inbound(self, db: Session, norm: NormalizedInboundMessage) -> None:
        users = UserRepository(db)
        ms_repo = MessagingSessionRepository(db)

        user = users.get_or_create_by_phone_e164(norm.from_e164)
        if not user.phone_e164:
            user.phone_e164 = norm.from_e164
            db.commit()

        ms = ms_repo.get_or_create(user_id=user.id, linq_chat_id=norm.chat_id)
        phone = norm.from_e164
        ctx = _OutboundCtx(phone=phone, chat_id=norm.chat_id, preferred_service=norm.preferred_service)

        if norm.media_urls and not _speech_backend():
            self._reply(ctx, REPLY_AUDIO_NO_TRANSCRIBER)
            return

        body = _body_from_message(norm)
        if body is None and norm.media_urls:
            self._reply(ctx, REPLY_TRANSCRIBE_FAILED)
            return
        if not body:
            self._reply(ctx, REPLY_EMPTY)
            return

        phase = str(ms.phase)

        if phase == MessagingWorkflowPhase.completed.value:
            if _wants_new_trip_after_done(body):
                self._reset(ms, ms_repo)
            else:
                self._reply(ctx, REPLY_THREAD_CLOSED)
                return
            phase = str(ms.phase)

        if _is_short_reset_phrase(body) and phase in (
            MessagingWorkflowPhase.collecting_intent.value,
            MessagingWorkflowPhase.awaiting_hotel_pick.value,
        ):
            self._reset(ms, ms_repo)
            self._reply(ctx, REPLY_DESTINATION)
            return

        if phase in (
            MessagingWorkflowPhase.awaiting_quote_approval.value,
            MessagingWorkflowPhase.calling_hotels.value,
        ):
            ms.phase = MessagingWorkflowPhase.collecting_intent.value
            ms_repo.save(ms)
            self._reply(ctx, REPLY_LEGACY_SESSION_RESET)
            return

        if phase == MessagingWorkflowPhase.awaiting_hotel_pick.value:
            self._on_hotel_pick(db, ms, user, body, ms_repo, ctx)
            return

        self._collect_intent(db, ms, user, body, ms_repo, ctx)

    def _collect_intent(
        self,
        db: Session,
        ms: MessagingSession,
        user: User,
        text: str,
        ms_repo: MessagingSessionRepository,
        ctx: _OutboundCtx,
    ) -> None:
        raw = ms.extra.get(_INTENT_LINES_KEY)
        lines = list(raw) if isinstance(raw, list) else []
        lines.append(text)
        combined = "\n".join(lines)

        try:
            spec = extract_trip_spec(combined, fill_default_dates=False)
        except RuntimeError:
            self._reply(ctx, REPLY_NEED_NVIDIA)
            return
        except Exception as e:
            logger.exception("trip extract failed")
            self._reply(ctx, REPLY_PARSE_ERROR.format(detail=e))
            return

        if not spec.destination:
            ms.extra = {**dict(ms.extra or {}), _INTENT_LINES_KEY: lines}
            ms_repo.save(ms)
            self._reply(ctx, REPLY_DESTINATION)
            return

        if spec.check_in is None or spec.check_out is None:
            ms.extra = {**dict(ms.extra or {}), _INTENT_LINES_KEY: lines}
            ms_repo.save(ms)
            self._reply(ctx, REPLY_NEED_DATES)
            return

        trips = TripRepository(db)
        upsert_trip_from_extracted_spec(trips, ms=ms, user=user, spec=spec)
        trip = trips.get_required(ms.trip_id)  # type: ignore[arg-type]
        merge_reference_location_into_trip(trips, trip, spec)

        try:
            hotels = HotelDiscoveryService(db).search(trip.id)
        except HotelDiscoveryFailed as e:
            self._reply(ctx, str(e)[:900])
            return
        if not hotels:
            self._reply(ctx, REPLY_NO_HOTELS)
            return

        ex = {**dict(ms.extra or {})}
        ex.pop(_INTENT_LINES_KEY, None)
        ex["hotel_ids"] = [str(h.id) for h in hotels]
        ms.extra = ex
        ms.phase = MessagingWorkflowPhase.awaiting_hotel_pick.value
        ms_repo.save(ms)

        self._send_hotel_list(db, ctx, trip.id, hotels)

    def _on_hotel_pick(
        self,
        db: Session,
        ms: MessagingSession,
        user: User,
        text: str,
        ms_repo: MessagingSessionRepository,
        ctx: _OutboundCtx,
    ) -> None:
        ids = list(ms.extra.get("hotel_ids") or [])
        if not ids or not ms.trip_id:
            ms.phase = MessagingWorkflowPhase.collecting_intent.value
            ms_repo.save(ms)
            self._reply(ctx, REPLY_RESET)
            return

        names = hotel_names_by_id(db, ids)
        picked = resolve_hotel_choice_by_name(text, ids, name_for_id=names)
        trip_id = ms.trip_id

        if picked is None:
            by_id = {str(h.id): h for h in HotelRepository(db).list_for_trip(trip_id)}
            ordered = [by_id[i] for i in ids if i in by_id]
            block = self._format_hotels(db, trip_id, ordered)
            self._reply(ctx, f"{RETRY_PICK_HEADER}\n\n{HEADER_OPTIONS}\n{block}\n\n{FOOTER_PICK}")
            return

        url = build_booking_com_payment_url(db, trip_id=trip_id, hotel_id=picked)
        ms.selected_hotel_id = picked
        ms.phase = MessagingWorkflowPhase.completed.value
        ms.extra = {**dict(ms.extra or {}), "payment_url": url, "selected_hotel_id": str(picked)}
        ms_repo.save(ms)
        self._reply(ctx, format_payment_link_message(url))

    def _send_hotel_list(
        self,
        db: Session,
        ctx: _OutboundCtx,
        trip_id: uuid.UUID,
        hotels: list[HotelCandidate],
    ) -> None:
        block = self._format_hotels(db, trip_id, hotels)
        self._reply(ctx, f"{HEADER_OPTIONS}\n{block}\n{FOOTER_PICK}")

    def _format_hotels(self, db: Session, trip_id: uuid.UUID, hotels: list[HotelCandidate]) -> str:
        quotes = QuoteRepository(db).list_for_trip(trip_id)
        by_hotel = {q.hotel_id: q for q in quotes}
        return format_hotel_option_lines(hotel_sms_rows(hotels, by_hotel))

    @staticmethod
    def _reset(ms: MessagingSession, ms_repo: MessagingSessionRepository) -> None:
        ms.phase = MessagingWorkflowPhase.collecting_intent.value
        ms.trip_id = None
        ms.selected_hotel_id = None
        ms.selected_quote_id = None
        ms.extra = {}
        ms_repo.save(ms)
