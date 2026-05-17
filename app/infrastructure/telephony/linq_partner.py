from __future__ import annotations

import httpx

from app.core.config import settings


def normalize_linq_base_url(base_url: str) -> str:
    """Partner API root only — no trailing /chats (avoids POST …/chats/chats)."""
    base = base_url.rstrip("/")
    if base.endswith("/chats"):
        base = base[: -len("/chats")].rstrip("/")
    return base


class LinqPartnerClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.linq_api_key
        raw = base_url if base_url is not None else settings.linq_base_url
        self._base_url = normalize_linq_base_url(raw)

    @property
    def base_url(self) -> str:
        return self._base_url

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def authorization_headers(self) -> dict[str, str]:
        if not self._api_key:
            return {}
        return {"Authorization": f"Bearer {self._api_key}"}

    def send_text_message(self, *, to_e164: str, text: str, from_e164: str | None = None) -> httpx.Response:
        from_num = from_e164 or settings.linq_from_number
        if not from_num:
            raise RuntimeError("LINQ_FROM_NUMBER not configured")
        if not self._api_key:
            raise RuntimeError("LINQ_API_KEY not configured")
        payload = {
            "from": from_num,
            "to": [to_e164],
            "message": {"parts": [{"type": "text", "value": text}]},
        }
        url = f"{self._base_url}/chats"
        return httpx.post(
            url,
            json=payload,
            headers={
                **self.authorization_headers(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    def send_message_in_chat(
        self,
        *,
        chat_id: str,
        text: str,
        preferred_service: str | None = None,
    ) -> httpx.Response:
        """Reply in an existing thread (required for SMS delivery with URLs)."""
        if not self._api_key:
            raise RuntimeError("LINQ_API_KEY not configured")
        payload: dict = {"message": {"parts": [{"type": "text", "value": text}]}}
        if preferred_service:
            payload["preferred_service"] = preferred_service
        url = f"{self._base_url}/chats/{chat_id}/messages"
        return httpx.post(
            url,
            json=payload,
            headers={
                **self.authorization_headers(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )
