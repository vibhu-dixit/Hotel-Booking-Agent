from __future__ import annotations

import hashlib
import json
from datetime import datetime

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IdempotencyKey, IdempotencyStatus


IDEMPOTENCY_HEADER = "Idempotency-Key"


def _hash_request(method: str, path: str, body: bytes) -> str:
    h = hashlib.sha256()
    h.update(method.upper().encode("utf-8"))
    h.update(b"\n")
    h.update(path.encode("utf-8"))
    h.update(b"\n")
    h.update(body)
    return h.hexdigest()


def maybe_return_idempotent_response(
    db: Session, *, key: str, route: str, request_hash: str
) -> Response | None:
    existing = db.execute(
        select(IdempotencyKey).where(IdempotencyKey.key == key, IdempotencyKey.route == route)
    ).scalar_one_or_none()
    if existing is None:
        return None

    if existing.request_hash != request_hash:
        return Response(
            status_code=409,
            content=json.dumps({"detail": "Idempotency-Key reuse with different request payload."}),
            media_type="application/json",
        )

    if existing.status == IdempotencyStatus.completed and existing.response_json is not None:
        return Response(
            status_code=200,
            content=json.dumps(existing.response_json),
            media_type="application/json",
        )

    return Response(
        status_code=202,
        content=json.dumps({"detail": "Request already in progress."}),
        media_type="application/json",
    )


def register_idempotency_start(
    db: Session, *, key: str, route: str, request_hash: str, user_id
) -> IdempotencyKey:
    rec = IdempotencyKey(
        user_id=user_id,
        key=key,
        route=route,
        request_hash=request_hash,
        status=IdempotencyStatus.started,
        response_json=None,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def complete_idempotency(
    db: Session, *, key: str, route: str, response_json: dict, succeeded: bool
) -> None:
    rec = db.execute(select(IdempotencyKey).where(IdempotencyKey.key == key, IdempotencyKey.route == route)).scalar_one()
    rec.status = IdempotencyStatus.completed if succeeded else IdempotencyStatus.failed
    rec.response_json = response_json
    rec.completed_at = datetime.utcnow()
    db.commit()


async def idempotency_guard(
    request: Request,
    response: Response,
    *,
    db: Session,
    user_id=None,
    enable_for_methods: set[str] | None = None,
) -> Response | None:
    methods = enable_for_methods or {"POST"}
    if request.method.upper() not in methods:
        return None

    key = request.headers.get(IDEMPOTENCY_HEADER)
    if not key:
        return None

    body = await request.body()
    req_hash = _hash_request(request.method, request.url.path, body)

    cached = maybe_return_idempotent_response(db, key=key, route=request.url.path, request_hash=req_hash)
    if cached is not None:
        return cached

    # Best-effort insert; if a race happens, subsequent request will see it.
    register_idempotency_start(db, key=key, route=request.url.path, request_hash=req_hash, user_id=user_id)
    return None

