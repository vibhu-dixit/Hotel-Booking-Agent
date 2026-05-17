from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.application.scoring.quote_scorer import normalize_ranking_priority
from app.core.json_utils import strip_json_fence
from app.infrastructure.ai.nvidia_llm import chat_response_text


@dataclass
class ExtractedTripSpec:
    destination: str | None
    check_in: date | None
    check_out: date | None
    guests: int
    rooms: int
    budget_total: float | None
    currency: str
    reference_location: str | None
    amenities: list[str]
    chain_loyalty: dict[str, Any]
    preferences: dict[str, Any]
    constraints: dict[str, Any]
    missing: list[str]
    notes: str | None


def _default_system() -> str:
    today = date.today().isoformat()
    return f"""You extract structured hotel trip intent from the user's message(s). Return ONLY valid JSON, no markdown.

Today's date is {today}. Resolve all relative and spoken dates against this anchor (e.g. "tomorrow", "next Friday", "May 18–20", "the 18th to the 20th").
If the user gives month/day without a year, pick the next future occurrence on or after today (same year when still upcoming, otherwise next year).
check_out must be strictly after check_in.

Use keys:
- destination (string, city/area to stay)
- check_in, check_out (ISO date YYYY-MM-DD if inferable, else null)
- guests (int, default 2), rooms (int, default 1)
- budget_total (number or null), currency (string, default USD)
- reference_location (string landmark/address for "near X" distance, or null)
- amenities (array of strings, e.g. non_smoking, parking)
- chain_loyalty (object: chain string optional, member_id string optional)
- missing (array of field names still required: destination, check_in, check_out are mandatory for a complete trip)
- notes (short string)
- ranking_priority (string optional): what matters most when comparing hotels — lowest_price | budget_fit | highest_rating | closest | balanced (or informal: cheap, budget, stars, near)

If dates are missing, set missing to include check_in/check_out. Do not substitute "tomorrow" unless the user clearly asked for tomorrow."""


def extract_trip_spec(user_text: str, *, fill_default_dates: bool = True) -> ExtractedTripSpec:
    raw = chat_response_text(
        messages=[
            {"role": "system", "content": _default_system()},
            {"role": "user", "content": user_text[:12000]},
        ],
        temperature=0.1,
        max_tokens=2048,
    )
    try:
        data = json.loads(strip_json_fence(raw))
    except json.JSONDecodeError:
        data = {}

    dest = data.get("destination")
    if isinstance(dest, str):
        dest = dest.strip() or None
    else:
        dest = None

    ci = _parse_date(data.get("check_in"))
    co = _parse_date(data.get("check_out"))
    ci, co = _coerce_future_stay_dates(ci, co, date.today())
    guests = _int_or(data.get("guests"), 2)
    rooms = _int_or(data.get("rooms"), 1)
    budget = data.get("budget_total")
    budget_f = float(budget) if isinstance(budget, (int, float)) else None
    currency = str(data.get("currency") or "USD")[:8]

    ref = data.get("reference_location")
    ref_s = str(ref).strip() if ref else None

    amenities = data.get("amenities")
    if not isinstance(amenities, list):
        amenities = []
    amenities_s = [str(a) for a in amenities if a]

    loyalty = data.get("chain_loyalty")
    if not isinstance(loyalty, dict):
        loyalty = {}

    missing = data.get("missing")
    if not isinstance(missing, list):
        missing = []
    missing_s = [str(m) for m in missing]

    prefs: dict = {"amenities": amenities_s}
    if loyalty.get("chain"):
        prefs["loyalty"] = loyalty

    rp = data.get("ranking_priority")
    if rp is not None and str(rp).strip():
        prefs["ranking_priority"] = normalize_ranking_priority(str(rp))

    constraints: dict = {}
    for a in amenities_s:
        al = a.lower().replace(" ", "_")
        if "non_smok" in al or "non-smok" in al:
            constraints["non_smoking"] = True
        if "breakfast" in al:
            constraints["breakfast_included"] = True

    if not dest:
        missing_s.append("destination")

    # web fills default dates; Linq passes fill_default_dates=False to ask follow-ups
    if fill_default_dates:
        base = date.today()
        if ci is None and dest:
            ci = base + timedelta(days=7)
        if co is None and ci:
            co = ci + timedelta(days=1)

    notes = data.get("notes")
    notes_s = str(notes)[:500] if notes else None

    return ExtractedTripSpec(
        destination=dest,
        check_in=ci,
        check_out=co,
        guests=guests,
        rooms=rooms,
        budget_total=budget_f,
        currency=currency,
        reference_location=ref_s,
        amenities=amenities_s,
        chain_loyalty=loyalty,
        preferences=prefs,
        constraints=constraints,
        missing=list(dict.fromkeys(missing_s)),
        notes=notes_s,
    )


def _coerce_future_stay_dates(
    check_in: date | None,
    check_out: date | None,
    today: date,
) -> tuple[date | None, date | None]:
    """Bump past years / fix checkout so links match what the user asked for."""
    if check_in is None:
        return check_in, check_out
    ci = check_in
    while ci < today:
        try:
            ci = ci.replace(year=ci.year + 1)
        except ValueError:
            ci = ci + timedelta(days=365)
    if check_out is None:
        return ci, None
    co = check_out
    while co <= ci:
        try:
            co = co.replace(year=co.year + 1)
        except ValueError:
            co = co + timedelta(days=365)
    if co <= ci:
        co = ci + timedelta(days=1)
    return ci, co


def _parse_date(v: object) -> date | None:
    if v is None:
        return None
    if isinstance(v, str):
        try:
            y, m, d = v.strip()[:10].split("-")
            return date(int(y), int(m), int(d))
        except Exception:
            return None
    return None


def _int_or(v: object, default: int) -> int:
    try:
        return int(v)  # type: ignore[arg-type]
    except Exception:
        return default
