from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_LISTEN = "https://api.deepgram.com/v1/listen"


class DeepgramSpeechTranscriptionAdapter:
    def transcribe_bytes(self, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        if not settings.deepgram_api_key or not data:
            return ""
        return self._post(data, content_type=content_type)

    def transcribe_media_url(self, url: str) -> str:
        if not settings.deepgram_api_key:
            return ""
        headers = {"Authorization": f"Token {settings.deepgram_api_key}"}
        params = {"model": settings.deepgram_listen_model, "smart_format": "true", "punctuate": "true"}
        try:
            with httpx.Client(timeout=120.0) as client:
                r = client.post(
                    _LISTEN,
                    params=params,
                    headers={**headers, "Content-Type": "application/json"},
                    json={"url": url},
                )
                r.raise_for_status()
                return _text(r.json())
        except Exception as e:
            logger.info("deepgram url failed, downloading: %s", e)
        try:
            with httpx.Client(timeout=120.0, follow_redirects=True) as client:
                media = client.get(url)
                media.raise_for_status()
                ct = media.headers.get("content-type", "application/octet-stream").split(";")[0]
                return self._post(media.content, content_type=ct, headers=headers, params=params)
        except Exception as e:
            logger.warning("deepgram failed: %s", e)
            return ""

    def _post(
        self,
        body: bytes,
        *,
        content_type: str,
        headers: dict | None = None,
        params: dict | None = None,
    ) -> str:
        headers = headers or {"Authorization": f"Token {settings.deepgram_api_key}"}
        params = params or {
            "model": settings.deepgram_listen_model,
            "smart_format": "true",
            "punctuate": "true",
        }
        with httpx.Client(timeout=120.0) as client:
            r = client.post(_LISTEN, params=params, headers={**headers, "Content-Type": content_type}, content=body)
            r.raise_for_status()
            return _text(r.json())


def _text(payload: object) -> str:
    try:
        return payload["results"]["channels"][0]["alternatives"][0]["transcript"].strip()  # type: ignore[index]
    except (KeyError, IndexError, AttributeError, TypeError):
        return ""
