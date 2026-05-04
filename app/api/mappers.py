from __future__ import annotations

from app.db.models import HotelCandidate, Quote


def hotel_candidate_to_dict(h: HotelCandidate, *, quote: Quote | None = None) -> dict:
    """API boundary mapping (DRY — one place for hotel projection)."""
    out: dict = {
        "id": h.id,
        "name": h.name,
        "address": h.address,
        "phone_e164": h.phone_e164,
        "metadata": h.extra_metadata,
        "nightly_rate": None,
        "taxes_fees": None,
        "total_price": None,
        "currency": None,
    }
    if quote is not None:
        out["nightly_rate"] = float(quote.nightly_rate) if quote.nightly_rate is not None else None
        out["taxes_fees"] = float(quote.taxes_fees) if quote.taxes_fees is not None else None
        out["total_price"] = float(quote.total_price) if quote.total_price is not None else None
        out["currency"] = quote.currency or None
    return out
