from __future__ import annotations

from decimal import Decimal


def normalize_quote_fields(extracted: dict) -> dict:
    """
    Convert loosely extracted facts into normalized quote fields.
    Deterministic; LLM extraction stays upstream.
    """
    out: dict = {}
    if "total_price" in extracted and extracted["total_price"] is not None:
        out["total_price"] = Decimal(str(extracted["total_price"]))
    if "nightly_rate" in extracted and extracted["nightly_rate"] is not None:
        out["nightly_rate"] = Decimal(str(extracted["nightly_rate"]))
    if "taxes_fees" in extracted and extracted["taxes_fees"] is not None:
        out["taxes_fees"] = Decimal(str(extracted["taxes_fees"]))
    return out
