from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.infrastructure.persistence.repositories import HotelRepository


def hotel_names_by_id(db: Session, hotel_ids: list[str]) -> dict[str, str]:
    """Map candidate id string → display name for fuzzy pick matching."""
    hr = HotelRepository(db)
    out: dict[str, str] = {}
    for hid in hotel_ids:
        try:
            uid = uuid.UUID(hid)
        except ValueError:
            continue
        out[hid] = hr.get_required(uid).name
    return out
