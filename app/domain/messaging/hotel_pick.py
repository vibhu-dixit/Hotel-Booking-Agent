from __future__ import annotations

import re
import unicodedata
import uuid


def resolve_hotel_choice(user_text: str, hotel_ids: list[str]) -> uuid.UUID | None:
    """Pick a hotel by 1-based index or case-insensitive substring match on name (requires hotel lookup by caller)."""
    t = unicodedata.normalize("NFKC", user_text).strip()
    m_idx = re.match(r"^#?(\d+)\s*$", t)
    if m_idx:
        t = m_idx.group(1)
    if t.isdigit():
        idx = int(t) - 1
        if 0 <= idx < len(hotel_ids):
            try:
                return uuid.UUID(hotel_ids[idx])
            except ValueError:
                return None
    return None


def resolve_hotel_choice_by_name(
    user_text: str,
    hotel_ids: list[str],
    *,
    name_for_id: dict[str, str],
) -> uuid.UUID | None:
    """Match substring against precomputed id → hotel name map."""
    by_index = resolve_hotel_choice(user_text, hotel_ids)
    if by_index is not None:
        return by_index
    tl = unicodedata.normalize("NFKC", user_text).strip().lower()
    if not tl:
        return None
    for hid, name in name_for_id.items():
        if tl in name.lower():
            try:
                return uuid.UUID(hid)
            except ValueError:
                continue
    return None
