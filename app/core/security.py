from __future__ import annotations

import re


_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]*?){13,19}(?!\d)")


def redact_pci(text: str) -> str:
    return _CARD_RE.sub("[REDACTED_CARD]", text)

