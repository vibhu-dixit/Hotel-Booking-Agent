"""Single source for Linq-facing user strings (DRY)."""

from __future__ import annotations

REPLY_DESTINATION = "Where do you want to stay (city or neighborhood)?"
REPLY_NEED_DATES = (
    "What are your check-in and check-out dates? "
    '(e.g. "May 13–15, 2026", "next Friday for 2 nights", or "Mar 3 check-in, Mar 6 out").'
)
REPLY_NEED_NVIDIA = "Natural language booking needs NVIDIA_API_KEY configured on the server."
REPLY_PARSE_ERROR = "Could not parse your request ({detail}). Try rephrasing."
REPLY_EMPTY = "Tell me your destination, dates, and any preferences."
REPLY_THREAD_CLOSED = (
    "That booking is already complete. Say hi, new trip, or send your destination and dates to search again."
)
REPLY_RESET = "Something reset — tell me your destination and dates."
REPLY_PICK_NUMBER = "Reply with a number 1–{n} from the list."
RETRY_PICK_HEADER = "We couldn't match that — here are the hotels again:"
REPLY_NO_HOTELS = "No hotels turned up for that search. Try another city or dates."
HEADER_OPTIONS = "Here are options:"
FOOTER_PICK = "Reply with a number to choose a hotel — we'll send you a secure payment link."

def format_payment_link_message(url: str) -> str:
    return f"Continue on Booking.com (dates & guests prefilled):\n{url}"


REPLY_LEGACY_SESSION_RESET = (
    "This chat used an older booking flow. Send your destination and dates again to search hotels."
)


def chunk_text_for_outbound(message: str, max_chars: int) -> list[str]:
    """Split long outbound text so SMS/iMessage gateways don't silently truncate."""

    def packed_len(lines_: list[str]) -> int:
        if not lines_:
            return 0
        return sum(len(x) for x in lines_) + len(lines_) - 1

    text = message.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    lines = text.split("\n")
    chunks: list[str] = []
    cur: list[str] = []

    for line in lines:
        piece = line
        while len(piece) > max_chars:
            if cur:
                chunks.append("\n".join(cur))
                cur = []
            chunks.append(piece[:max_chars])
            piece = piece[max_chars:]
        line = piece

        if packed_len(cur + [line]) <= max_chars:
            cur.append(line)
        else:
            if cur:
                chunks.append("\n".join(cur))
            cur = [line]

    if cur:
        chunks.append("\n".join(cur))
    return chunks


def format_hotel_option_lines(
    rows: list[tuple[str, object | None, str | None, str | None]],
) -> str:
    """Each row: (name, distance_km_or_none, price_summary_or_none, maps_uri_or_none)."""
    lines: list[str] = []
    for i, (name, km, price, maps_uri) in enumerate(rows, start=1):
        suf = f" ({km} km)" if km is not None else ""
        ps = f" — {price}" if price else ""
        lines.append(f"{i}. {name}{suf}{ps}")
        if isinstance(maps_uri, str) and maps_uri.strip():
            lines.append(f"   Photos & details: {maps_uri.strip()}")
    return "\n".join(lines)
