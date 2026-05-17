from __future__ import annotations

from app.domain.ports import IntentParserPort, ParsedIntent


class RuleBasedIntentParser(IntentParserPort):
    # keyword pass for web /intent/parse — cheap, no LLM

    def parse(self, user_text: str) -> ParsedIntent:
        text = user_text.lower()
        prefs: dict = {}
        constraints: dict = {}

        if "breakfast" in text:
            constraints["breakfast_included"] = True
        if "refundable" in text or "free cancellation" in text:
            constraints["refundable"] = True
        if "parking" in text:
            prefs["parking"] = True
        if "pool" in text:
            prefs["pool"] = True

        if any(p in text for p in ("cheapest", "lowest price", "lowest total", "best price", "save money")):
            prefs["ranking_priority"] = "lowest_price"
        elif any(p in text for p in ("stay under budget", "within budget", "fit my budget", "affordable")):
            prefs["ranking_priority"] = "budget_fit"
        elif any(p in text for p in ("best rated", "top rated", "highest rating", "best reviews")):
            prefs["ranking_priority"] = "highest_rating"
        elif any(p in text for p in ("closest", "nearest", "walking distance", "nearby")):
            prefs["ranking_priority"] = "closest"

        return ParsedIntent(preferences=prefs, constraints=constraints)
