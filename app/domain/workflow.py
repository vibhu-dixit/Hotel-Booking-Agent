from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass
from datetime import timedelta


class TripWorkflowState(str, enum.Enum):
    created = "created"
    intent_parsed = "intent_parsed"
    searched = "searched"
    calling = "calling"
    quoted = "quoted"
    evaluated = "evaluated"
    awaiting_approval = "awaiting_approval"
    booking = "booking"
    confirmed = "confirmed"
    failed = "failed"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    initial_backoff: timedelta
    max_backoff: timedelta


@dataclass(frozen=True)
class TimeoutPolicy:
    call_connect_timeout: timedelta
    max_call_duration: timedelta
    overall_workflow_timeout: timedelta


DEFAULT_RETRY = RetryPolicy(max_attempts=3, initial_backoff=timedelta(seconds=2), max_backoff=timedelta(seconds=30))
DEFAULT_TIMEOUTS = TimeoutPolicy(
    call_connect_timeout=timedelta(seconds=30),
    max_call_duration=timedelta(minutes=6),
    overall_workflow_timeout=timedelta(minutes=30),
)


def workflow_id(trip_id: uuid.UUID) -> str:
    """Deterministic workflow identifier for dedupe / future orchestrators."""
    return f"trip:{trip_id}"
