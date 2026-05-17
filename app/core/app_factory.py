from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.api.router import api_router
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.idempotency import IDEMPOTENCY_HEADER, complete_idempotency, idempotency_guard
from app.core.logging import configure_logging
from app.domain.exceptions import ApprovalRequiredError, HotelDiscoveryFailed

logger = logging.getLogger(__name__)
WEB_DIST = Path(__file__).resolve().parent.parent.parent / "web" / "dist"


def _log_linq_startup() -> None:
    if settings.linq_api_key and settings.linq_from_number:
        logger.info("Linq outbound OK (from %s)", settings.linq_from_number)
    else:
        logger.warning(
            "Linq outbound disabled — set LINQ_API_KEY and LINQ_FROM_NUMBER or SMS replies will not send"
        )
    if not settings.linq_webhook_secret:
        logger.warning("LINQ_WEBHOOK_SECRET empty — signature check skipped (fine for local dev only)")
    if not settings.nvidia_api_key:
        logger.warning("NVIDIA_API_KEY empty — Linq trip parsing will fail over SMS")
    logger.info(
        "Linq inbound: POST /webhooks/linq — must be public HTTPS (ngrok). Health: GET /webhooks/linq/health"
    )


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(title="Hotel Booking AI Agent")

    @app.on_event("startup")
    def _startup() -> None:
        _log_linq_startup()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApprovalRequiredError)
    async def approval_required_handler(_request: Request, exc: ApprovalRequiredError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(HotelDiscoveryFailed)
    async def hotel_discovery_failed_handler(_request: Request, exc: HotelDiscoveryFailed) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.middleware("http")
    async def error_translation(request: Request, call_next):
        try:
            return await call_next(request)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.middleware("http")
    async def idempotency(request: Request, call_next):
        if request.method.upper() != "POST":
            return await call_next(request)
        key = request.headers.get(IDEMPOTENCY_HEADER)
        if not key:
            return await call_next(request)

        body = await request.body()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request = Request(request.scope, receive)
        db: Session = SessionLocal()
        try:
            cached = await idempotency_guard(request, Response(), db=db, user_id=None)
            if cached is not None:
                return cached
            resp = await call_next(request)
            if resp.headers.get("content-type", "").startswith("application/json"):
                resp_body = b"".join([c async for c in resp.body_iterator])
                try:
                    payload = json.loads(resp_body.decode("utf-8") or "{}")
                except Exception:
                    payload = {"raw": resp_body.decode("utf-8", errors="replace")}
                complete_idempotency(
                    db, key=key, route=request.url.path, response_json=payload, succeeded=resp.status_code < 500
                )
                return Response(
                    content=resp_body,
                    status_code=resp.status_code,
                    headers=dict(resp.headers),
                    media_type="application/json",
                )
            complete_idempotency(
                db,
                key=key,
                route=request.url.path,
                response_json={"status_code": resp.status_code},
                succeeded=resp.status_code < 500,
            )
            return resp
        finally:
            db.close()

    app.include_router(api_router)

    assets = WEB_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="ui_assets")

    @app.get("/", response_model=None)
    def spa_index() -> FileResponse | JSONResponse:
        index = WEB_DIST / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(
            {"detail": "Web UI not built. cd web && npm run build, or use /docs."},
            status_code=404,
        )

    return app
