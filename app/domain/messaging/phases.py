from __future__ import annotations

from enum import Enum


class MessagingWorkflowPhase(str, Enum):
    """Persisted on MessagingSession.phase — values must stay stable for DB rows."""

    collecting_intent = "collecting_intent"
    awaiting_hotel_pick = "awaiting_hotel_pick"
    calling_hotels = "calling_hotels"
    awaiting_quote_approval = "awaiting_quote_approval"
    completed = "completed"
