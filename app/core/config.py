from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    database_url: str

    telephony_provider: str = "linq"
    # Linq Partner API: https://docs.linqapp.com/ (Bearer token; iMessage, RCS, SMS, voice)
    linq_api_key: str | None = None
    linq_base_url: str = "https://api.linqapp.com/api/partner/v3"
    linq_from_number: str | None = None
    linq_webhook_secret: str | None = None
    # Long SMS/iMessage bodies are often truncated; split outbound text into smaller parts.
    linq_outbound_chunk_chars: int = 1200
    # Brief pause between chunks so the carrier delivers them in order.
    linq_outbound_chunk_delay_s: float = 0.35

    hotel_discovery_provider: str = "stub"
    google_maps_api_key: str | None = None
    # Google Places Text Search: restrict results to this radius (miles) from destination or reference geocode
    hotel_search_radius_miles: float = 10.0
    # Max hotels returned to UI / Linq (top N after relevance + distance filter)
    hotel_search_max_results: int = 4

    intent_parser_provider: str = "llm"

    # Booking.com Partner Programme affiliate id (optional `aid=` on search URLs)
    booking_com_affiliate_id: str | None = None

    caller_id_mode: str = "verified_business_number"

    storage_provider: str = "local"
    local_storage_dir: str = ".local_storage"

    llm_provider: str | None = None
    llm_api_key: str | None = None
    asr_provider: str | None = None
    asr_api_key: str | None = None
    tts_provider: str | None = None
    tts_api_key: str | None = None

    hf_token: str | None = None
    hf_inference_provider: str = "fal-ai"
    hf_tts_model: str = "hexgrad/Kokoro-82M"
    hf_asr_model: str = "openai/whisper-large-v3"

    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_chat_model: str = "nvidia/nemotron-3-super-120b-a12b"

    audio_retention_days: int = 7
    transcript_retention_days: int = 30


settings = Settings()  # type: ignore[call-arg]

