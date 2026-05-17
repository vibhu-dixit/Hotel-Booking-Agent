from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.application.linq_booking_orchestrator import LinqBookingOrchestrator
from app.core.config import settings
from app.core.db import SessionLocal
from app.infrastructure.persistence.repositories import LinqWebhookDedupRepository
from app.infrastructure.telephony.linq_payloads import NormalizedInboundMessage, normalize_message_received
from app.infrastructure.telephony.linq_webhook_verify import verify_linq_webhook_signature

logger = logging.getLogger(__name__)

router = APIRouter(tags=["linq"])
_orchestrator = LinqBookingOrchestrator()


def _handle(norm: NormalizedInboundMessage) -> None:
    db = SessionLocal()
    try:
        logger.info("linq processing from=%s chat=%s", norm.from_e164, norm.chat_id)
        _orchestrator.handle_inbound(db, norm)
    except Exception:
        logger.exception("linq handler failed")
    finally:
        db.close()


@router.get("/webhooks/linq/health")
def linq_health() -> dict:
    """Quick config check — hit this while uvicorn is running."""
    return {
        "webhook_post_url": "/webhooks/linq",
        "ready_to_receive": True,
        "can_send_replies": bool(settings.linq_api_key and settings.linq_from_number),
        "linq_api_key_set": bool(settings.linq_api_key),
        "linq_from_number_set": bool(settings.linq_from_number),
        "linq_webhook_secret_set": bool(settings.linq_webhook_secret),
        "nvidia_api_key_set": bool(settings.nvidia_api_key),
        "deepgram_api_key_set": bool(settings.deepgram_api_key),
        "google_maps_configured": bool(settings.google_maps_api_key),
        "hotel_discovery_provider": settings.hotel_discovery_provider,
        "note": "Texting your Linq number only works if Linq can POST to this server (use ngrok in dev).",
    }


@router.post("/webhooks/linq")
async def linq_inbound(request: Request, background_tasks: BackgroundTasks) -> dict:
    raw = await request.body()
    event_header = request.headers.get("X-Webhook-Event")
    logger.info("linq webhook hit (%s bytes, X-Webhook-Event=%s)", len(raw), event_header)

    sig = request.headers.get("X-Webhook-Signature")
    ts = request.headers.get("X-Webhook-Timestamp")
    if not verify_linq_webhook_signature(raw_body=raw, timestamp=ts, signature=sig):
        logger.warning(
            "linq webhook rejected: bad signature (check LINQ_WEBHOOK_SECRET matches Linq dashboard)"
        )
        raise HTTPException(status_code=401, detail="invalid webhook signature")

    try:
        body = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="invalid json") from e

    event_type = body.get("event_type") or event_header
    event_id = body.get("event_id")

    if isinstance(event_id, str) and event_id:
        db = SessionLocal()
        try:
            if not LinqWebhookDedupRepository(db).try_acquire(event_id):
                logger.info("linq webhook deduped event_id=%s", event_id)
                return {"ok": True, "deduped": True}
        finally:
            db.close()

    if event_type == "message.failed":
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        logger.warning("linq message.failed: %s", data.get("failure_reason") or data)
        return {"ok": True}

    if event_type != "message.received":
        logger.info("linq webhook ignored event_type=%s", event_type)
        return {"ok": True, "ignored": event_type}

    norm = normalize_message_received(body.get("data"))
    if not norm:
        logger.warning("linq webhook: could not parse message.received payload")
        return {"ok": True, "parse_failed": True}

    from_num = settings.linq_from_number
    if from_num and norm.from_e164.replace(" ", "") == from_num.replace(" ", ""):
        logger.info("linq webhook ignored (echo from our own LINQ_FROM_NUMBER)")
        return {"ok": True, "ignored": "own_number"}

    background_tasks.add_task(_handle, norm)
    return {"ok": True}
