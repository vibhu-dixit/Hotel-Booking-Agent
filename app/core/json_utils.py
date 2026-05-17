from __future__ import annotations

import re


def strip_json_fence(text: str) -> str:
    """Remove markdown code fences from LLM JSON responses."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()
