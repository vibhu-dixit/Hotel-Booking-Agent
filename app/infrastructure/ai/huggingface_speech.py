from __future__ import annotations

import os
import tempfile
from pathlib import Path

from huggingface_hub import InferenceClient

from app.core.config import settings


class HuggingFaceSpeechGateway:
    """ASR/TTS via Hugging Face InferenceClient + provider (e.g. fal-ai)."""

    def __init__(self) -> None:
        self._client: InferenceClient | None = None
        if settings.hf_token:
            self._client = InferenceClient(provider=settings.hf_inference_provider, api_key=settings.hf_token)

    @property
    def available(self) -> bool:
        return self._client is not None

    def text_to_speech(self, text: str) -> bytes:
        if not self._client:
            raise RuntimeError("HF_TOKEN not configured")
        audio = self._client.text_to_speech(text, model=settings.hf_tts_model)
        if isinstance(audio, bytes):
            return audio
        raise TypeError(f"Unexpected TTS payload type: {type(audio)!r}")

    def transcribe_path(self, audio_path: str | Path) -> str:
        """Transcribe from a path (e.g. flac/wav/mp3 per model support)."""
        if not self._client:
            raise RuntimeError("HF_TOKEN not configured")
        output = self._client.automatic_speech_recognition(str(audio_path), model=settings.hf_asr_model)
        return self._normalize_asr(output)

    def transcribe_upload(self, data: bytes, suffix: str = ".wav") -> str:
        """Write bytes to temp file then transcribe (InferenceClient expects a path here)."""
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        try:
            Path(path).write_bytes(data)
            return self.transcribe_path(path)
        finally:
            Path(path).unlink(missing_ok=True)

    @staticmethod
    def _normalize_asr(output: object) -> str:
        if hasattr(output, "text"):
            return str(output.text)
        if isinstance(output, dict) and "text" in output:
            return str(output["text"])
        return str(output)


_gateway: HuggingFaceSpeechGateway | None = None


def speech_gateway() -> HuggingFaceSpeechGateway:
    global _gateway
    if _gateway is None:
        _gateway = HuggingFaceSpeechGateway()
    return _gateway
