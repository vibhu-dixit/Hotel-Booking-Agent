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
_orch = LinqBookingOrchestrator()


def _dispatch_inbound(norm: NormalizedInboundMessage) -> None:
    db = SessionLocal()
    try:
        _orch.handle_inbound(db, norm)
    except Exception:
        logger.exception("linq orchestrator failed")
    finally:
        db.close()


@router.post("/webhooks/linq")
async def linq_inbound(request: Request, background_tasks: BackgroundTasks) -> dict[str, object]:
    raw = await request.body()
    logger.info("linq webhook: POST received (%s bytes)", len(raw))
    sig = request.headers.get("X-Webhook-Signature")
    ts = request.headers.get("X-Webhook-Timestamp")
    if not verify_linq_webhook_signature(raw_body=raw, timestamp=ts, signature=sig):
        logger.warning(
            "linq webhook: invalid signature (set LINQ_WEBHOOK_SECRET to the subscription signing secret, or empty for local-only testing)"
        )
        raise HTTPException(status_code=401, detail="invalid webhook signature")

    try:
        body = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="invalid json") from e

    event_id = body.get("event_id")
    if isinstance(event_id, str) and event_id:
        db = SessionLocal()
        try:
            if not LinqWebhookDedupRepository(db).try_acquire(event_id):
                return {"ok": True, "deduped": True}
        finally:
            db.close()

    if body.get("event_type") != "message.received":
        return {"ok": True}

    norm = normalize_message_received(body.get("data"))
    if not norm:
        return {"ok": True}

    from_num = settings.linq_from_number
    if from_num and norm.from_e164.replace(" ", "") == from_num.replace(" ", ""):
        return {"ok": True}

    background_tasks.add_task(_dispatch_inbound, norm)
    return {"ok": True}
