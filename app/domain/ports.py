from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.db.models import CallSession, Quote


@dataclass(frozen=True)
class ParsedIntent:
    preferences: dict
    constraints: dict


class IntentParserPort(Protocol):
    def parse(self, user_text: str) -> ParsedIntent: ...


class HotelOutboundPort(Protocol):
    def run_quote_call(
        self,
        db: Session,
        *,
        trip_id: uuid.UUID,
        hotel_id: uuid.UUID,
    ) -> tuple[CallSession, Quote]: ...


class ChannelMessagingPort(Protocol):
    def send_text(
        self,
        to_e164: str,
        message: str,
        *,
        chat_id: str | None = None,
        preferred_service: str | None = None,
    ) -> None: ...


class SpeechTranscriptionPort(Protocol):
    def transcribe_media_url(self, url: str) -> str: ...
