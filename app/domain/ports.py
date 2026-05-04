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
    """Strategy for turning natural language into structured trip constraints."""

    def parse(self, user_text: str) -> ParsedIntent:
        ...


class HotelOutboundPort(Protocol):
    """Places an outbound call to a hotel and produces a quote (PSTN or simulated)."""

    def run_quote_call(
        self,
        db: "Session",
        *,
        trip_id: uuid.UUID,
        hotel_id: uuid.UUID,
    ) -> tuple["CallSession", "Quote"]:
        ...


class ChannelMessagingPort(Protocol):
    """Outbound user notifications (SMS/iMessage/RCS via Linq or another provider)."""

    def send_text(self, to_e164: str, message: str) -> None:
        """Best-effort send; implementations log failures rather than raising for UX flows."""
        ...


class SpeechTranscriptionPort(Protocol):
    """Download audio from URL and return transcript text."""

    def transcribe_media_url(self, url: str) -> str:
        ...
