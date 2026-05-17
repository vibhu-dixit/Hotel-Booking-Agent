from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

from app.api.schemas import AiChatRequest, AiChatResponse, AiTtsRequest, AiTranscribeResponse
from app.core.config import settings
from app.infrastructure.ai.deepgram_speech import DeepgramSpeechTranscriptionAdapter
from app.infrastructure.ai.huggingface_speech import speech_gateway
from app.infrastructure.ai.nvidia_llm import chat_complete, stream_chat

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/tts")
def tts(req: AiTtsRequest) -> Response:
    gw = speech_gateway()
    if not gw.available:
        raise HTTPException(status_code=503, detail="HF_TOKEN not configured")
    try:
        audio = gw.text_to_speech(req.text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return Response(content=audio, media_type="application/octet-stream")


@router.post("/transcribe", response_model=AiTranscribeResponse)
async def transcribe(file: UploadFile = File(...)) -> AiTranscribeResponse:
    data = await file.read()
    suffix = Path(file.filename or "upload.wav").suffix or ".wav"
    content_type = file.content_type or "application/octet-stream"

    if settings.deepgram_api_key:
        try:
            text = DeepgramSpeechTranscriptionAdapter().transcribe_bytes(data, content_type=content_type)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return AiTranscribeResponse(text=text)

    gw = speech_gateway()
    if not gw.available:
        raise HTTPException(status_code=503, detail="DEEPGRAM_API_KEY or HF_TOKEN required for transcription")
    try:
        text = gw.transcribe_upload(data, suffix=suffix)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AiTranscribeResponse(text=text)


@router.post("/chat", response_model=None)
def chat(req: AiChatRequest) -> AiChatResponse | StreamingResponse:
    if not settings.nvidia_api_key:
        raise HTTPException(status_code=503, detail="NVIDIA_API_KEY not configured")

    messages = [m.model_dump() for m in req.messages]
    if req.stream:

        def gen() -> bytes:
            for chunk in stream_chat(
                messages=messages,
                temperature=req.temperature,
                top_p=req.top_p,
                max_tokens=req.max_tokens,
            ):
                yield chunk.encode("utf-8")

        return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")

    try:
        text = chat_complete(
            messages=messages,
            temperature=req.temperature,
            top_p=req.top_p,
            max_tokens=req.max_tokens,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AiChatResponse(text=text)
