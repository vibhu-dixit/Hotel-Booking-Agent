from __future__ import annotations

from decimal import Decimal

from app.db.models import HotelCandidate, Quote, TripRequest

_VALID_PRIORITIES = frozenset(
    {"lowest_price", "budget_fit", "highest_rating", "closest", "balanced"}
)


def normalize_ranking_priority(raw: str | None) -> str:
    """Map UI / LLM / informal text to a stable priority key."""
    if not raw or not str(raw).strip():
        return "balanced"
    s = str(raw).strip().lower().replace(" ", "_").replace("-", "_")
    if s in _VALID_PRIORITIES:
        return s
    aliases = {
        "cheap": "lowest_price",
        "cheapest": "lowest_price",
        "price": "lowest_price",
        "cost": "lowest_price",
        "money": "lowest_price",
        "budget": "budget_fit",
        "under_budget": "budget_fit",
        "affordable": "budget_fit",
        "stars": "highest_rating",
        "rating": "highest_rating",
        "rated": "highest_rating",
        "quality": "highest_rating",
        "distance": "closest",
        "near": "closest",
        "nearby": "closest",
        "location": "closest",
        "proximity": "closest",
        "walk": "closest",
        "default": "balanced",
        "mix": "balanced",
        "overall": "balanced",
    }
    return aliases.get(s, "balanced")


def trip_ranking_priority(trip: TripRequest) -> str:
    prefs = trip.preferences if isinstance(trip.preferences, dict) else {}
    return normalize_ranking_priority(prefs.get("ranking_priority"))


class QuoteScorer:
    """Scores quotes for ranking; weights depend on ``trip.preferences["ranking_priority"]``."""

    def score(self, trip: TripRequest, hotel: HotelCandidate, quote: Quote) -> tuple[float, dict]:
        priority = trip_ranking_priority(trip)
        reasons: dict = {"components": [], "priority": priority}

        rating = float(hotel.extra_metadata.get("rating", 0.0) or 0.0)
        total_f = float(quote.total_price) if quote.total_price is not None else None

        dist = hotel.extra_metadata.get("distance_km") if isinstance(hotel.extra_metadata, dict) else None
        d_km: float | None = None
        if dist is not None:
            try:
                d_km = float(dist)
            except (TypeError, ValueError):
                d_km = None

        refundable_required = bool(trip.constraints.get("refundable"))
        refundable = bool(quote.cancellation.get("refundable")) if isinstance(quote.cancellation, dict) else False

        score = 0.0

        if priority == "lowest_price":
            if total_f is not None:
                # Lower price => higher score (dominant)
                score += max(0.0, 5000.0 - total_f * 15.0)
                reasons["components"].append({"name": "total_price_inverse", "value": total_f, "weight": score})
            score += rating * 3.0
            reasons["components"].append({"name": "rating", "value": rating, "weight": rating * 3.0})
            if d_km is not None:
                bonus = max(0.0, 5.0 - min(d_km, 5.0))
                score += bonus
                reasons["components"].append({"name": "distance_km", "value": d_km, "weight": bonus})

        elif priority == "budget_fit":
            if total_f is not None and trip.budget_total is not None:
                budget = Decimal(trip.budget_total)
                if Decimal(str(total_f)) <= budget:
                    score += 120.0
                    reasons["components"].append({"name": "budget", "value": "within_budget", "weight": 120.0})
                else:
                    over = float(Decimal(str(total_f)) - budget)
                    score -= min(120.0, 30.0 + over * 2.0)
                    reasons["components"].append({"name": "budget", "value": "over_budget", "weight": score})
            elif total_f is not None:
                score += max(0.0, 800.0 - total_f * 4.0)
                reasons["components"].append({"name": "price_without_budget_cap", "value": total_f, "weight": score})
            score += rating * 8.0
            reasons["components"].append({"name": "rating", "value": rating, "weight": rating * 8.0})
            if d_km is not None:
                bonus = max(0.0, 12.0 - min(d_km, 12.0))
                score += bonus
                reasons["components"].append({"name": "distance_km", "value": d_km, "weight": bonus})

        elif priority == "highest_rating":
            score += rating * 28.0
            reasons["components"].append({"name": "rating", "value": rating, "weight": rating * 28.0})
            if total_f is not None:
                score += max(0.0, 400.0 - total_f * 2.0)
                reasons["components"].append({"name": "price_mild", "value": total_f, "weight": max(0.0, 400.0 - total_f * 2.0)})
            if d_km is not None:
                bonus = max(0.0, 8.0 - min(d_km, 8.0))
                score += bonus
                reasons["components"].append({"name": "distance_km", "value": d_km, "weight": bonus})

        elif priority == "closest":
            if d_km is not None:
                bonus = max(0.0, 35.0 - min(d_km, 35.0))
                score += bonus
                reasons["components"].append({"name": "distance_km", "value": d_km, "weight": bonus})
            score += rating * 8.0
            reasons["components"].append({"name": "rating", "value": rating, "weight": rating * 8.0})
            if total_f is not None:
                score += max(0.0, 300.0 - total_f * 1.5)
                reasons["components"].append({"name": "price_mild", "value": total_f, "weight": max(0.0, 300.0 - total_f * 1.5)})

        else:  # balanced
            score += rating * 10.0
            reasons["components"].append({"name": "rating", "value": rating, "weight": rating * 10.0})

            if total_f is not None and trip.budget_total is not None:
                budget = Decimal(trip.budget_total)
                if Decimal(str(total_f)) <= budget:
                    score += 50.0
                    reasons["components"].append({"name": "budget", "value": "within_budget", "weight": 50.0})
                else:
                    score -= 50.0
                    reasons["components"].append({"name": "budget", "value": "over_budget", "weight": -50.0})

            if refundable_required and not refundable:
                score -= 100.0
                reasons["components"].append({"name": "refundable", "value": "missing", "weight": -100.0})
            elif refundable_required and refundable:
                score += 20.0
                reasons["components"].append({"name": "refundable", "value": "present", "weight": 20.0})

            if d_km is not None:
                bonus = max(0.0, 15.0 - min(d_km, 15.0))
                score += bonus
                reasons["components"].append({"name": "distance_km", "value": d_km, "weight": bonus})

            if bool(trip.constraints.get("non_smoking")):
                ns = str(hotel.extra_metadata.get("non_smoking", "")).lower() if isinstance(hotel.extra_metadata, dict) else ""
                if ns in ("true", "yes", "1"):
                    score += 10.0
                    reasons["components"].append({"name": "non_smoking", "value": True, "weight": 10.0})

        # Refundable penalty applies across priorities when user asked for it
        if priority != "balanced":
            if refundable_required and not refundable:
                score -= 80.0
                reasons["components"].append({"name": "refundable_penalty", "value": "missing", "weight": -80.0})
            elif refundable_required and refundable:
                score += 15.0
                reasons["components"].append({"name": "refundable_bonus", "value": "present", "weight": 15.0})

        return score, reasons
