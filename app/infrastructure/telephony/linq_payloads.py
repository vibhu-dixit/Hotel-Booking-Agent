from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedInboundMessage:
    chat_id: str
    from_e164: str
    text: str
    media_urls: list[str]


def normalize_message_received(data: object) -> NormalizedInboundMessage | None:
    """Support v3 nested `data` and legacy v2-style shapes."""
    if not isinstance(data, dict):
        return None
    chat_id = None
    if isinstance(data.get("chat"), dict):
        chat_id = data["chat"].get("id")
    if not chat_id:
        chat_id = data.get("chat_id")
    if not chat_id or not isinstance(chat_id, str):
        return None

    sender = None
    if isinstance(data.get("sender_handle"), dict):
        sender = data["sender_handle"].get("handle")
    if not sender:
        sender = data.get("from")
    if not isinstance(sender, str):
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

    return NormalizedInboundMessage(
        chat_id=chat_id,
        from_e164=sender,
        text="\n".join(texts).strip(),
        media_urls=media_urls,
    )
