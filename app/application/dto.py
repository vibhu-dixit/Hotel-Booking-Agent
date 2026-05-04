from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class TripStartResult:
    trip_id: uuid.UUID
    user_id: uuid.UUID
