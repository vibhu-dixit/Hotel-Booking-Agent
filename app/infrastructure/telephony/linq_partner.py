from __future__ import annotations

import httpx

from app.core.config import settings


class LinqPartnerClient:
    """Thin HTTP client for the Linq Partner API v3 (Bearer auth).

    Base URL and auth: https://docs.linqapp.com/getting-started/authentication/
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.linq_api_key
        self._base_url = (base_url if base_url is not None else settings.linq_base_url).rstrip("/")

    @property
    def base_url(self) -> str:
        return self._base_url

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def authorization_headers(self) -> dict[str, str]:
        if not self._api_key:
            return {}
        return {"Authorization": f"Bearer {self._api_key}"}

    def sync_client(self, *, timeout_s: float = 30.0) -> httpx.Client:
        return httpx.Client(
            base_url=self._base_url,
            headers={
                **self.authorization_headers(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=timeout_s,
        )

    def send_text_message(self, *, to_e164: str, text: str, from_e164: str | None = None) -> httpx.Response:
        """POST /chats — outbound SMS/iMessage per Partner API v3."""
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
        with self.sync_client() as client:
            return client.post("/chats", json=payload)
