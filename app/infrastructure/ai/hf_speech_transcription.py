from __future__ import annotations

import logging

import httpx

from app.infrastructure.ai.huggingface_speech import speech_gateway

logger = logging.getLogger(__name__)


class HuggingFaceSpeechTranscriptionAdapter:
    def transcribe_media_url(self, url: str) -> str:
        gw = speech_gateway()
        if not gw.available:
            return ""
        try:
            r = httpx.get(url, timeout=120.0, follow_redirects=True)
            r.raise_for_status()
            return gw.transcribe_upload(r.content, suffix=".m4a")
        except Exception as e:
            logger.warning("hf transcribe failed: %s", e)
            return ""
