from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NormalizedInboundMessage:
    chat_id: str
    from_e164: str
    text: str
    media_urls: list[str]
    preferred_service: str | None = None


def normalize_message_received(data: object) -> NormalizedInboundMessage | None:
    """Parse Linq `message.received` data (v3 2026-02-03 or legacy 2025-01-01 shapes)."""
    if not isinstance(data, dict):
        logger.warning("linq payload: data is not an object")
        return None

    if data.get("is_from_me") is True or data.get("direction") == "outbound":
        return None

    chat_id = None
    if isinstance(data.get("chat"), dict):
        chat_id = data["chat"].get("id")
    if not chat_id:
        chat_id = data.get("chat_id")
    if not chat_id or not isinstance(chat_id, str):
        logger.warning("linq payload: missing chat id")
        return None

    sender = None
    if isinstance(data.get("sender_handle"), dict):
        sender = data["sender_handle"].get("handle")
    if not sender and isinstance(data.get("from_handle"), dict):
        sender = data["from_handle"].get("handle")
    if not sender:
        sender = data.get("from")
    if not isinstance(sender, str):
        logger.warning("linq payload: missing sender handle")
        return None

    parts: list = []
    if isinstance(data.get("parts"), list):
        parts = data["parts"]
    elif isinstance(data.get("message"), dict) and isinstance(data["message"].get("parts"), list):
        parts = data["message"]["parts"]

    texts: list[str] = []
    media_urls: list[str] = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        t = p.get("type")
        if t == "text" and isinstance(p.get("value"), str):
            texts.append(p["value"])
        if t in ("media", "audio", "attachment") and isinstance(p.get("url"), str):
            media_urls.append(p["url"])

    part_types = [p.get("type") for p in parts if isinstance(p, dict)]
    if not texts and not media_urls:
        logger.warning("linq payload: no text or media parts (types=%s)", part_types)

    service = data.get("service") or data.get("preferred_service")
    if not isinstance(service, str):
        service = None

    return NormalizedInboundMessage(
        chat_id=chat_id,
        from_e164=sender,
        text="\n".join(texts).strip(),
        media_urls=media_urls,
        preferred_service=service,
    )
