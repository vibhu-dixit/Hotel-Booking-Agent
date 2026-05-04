from __future__ import annotations

import logging

import httpx

from app.domain.ports import SpeechTranscriptionPort
from app.infrastructure.ai.huggingface_speech import speech_gateway

logger = logging.getLogger(__name__)


class HuggingFaceSpeechTranscriptionAdapter:
    """SpeechTranscriptionPort: download URL → ASR via Hugging Face."""

    def transcribe_media_url(self, url: str) -> str:
        gw = speech_gateway()
        if not gw.available:
            return ""
        try:
            r = httpx.get(url, timeout=120.0, follow_redirects=True)
            r.raise_for_status()
            return gw.transcribe_upload(r.content, suffix=".m4a")
        except Exception as e:  # noqa: BLE001
            logger.warning("transcribe failed: %s", e)
            return ""
