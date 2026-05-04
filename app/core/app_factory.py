from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.api.router import api_router
from app.core.db import SessionLocal
from app.core.idempotency import IDEMPOTENCY_HEADER, complete_idempotency, idempotency_guard
from app.core.logging import configure_logging
from app.domain.exceptions import ApprovalRequiredError, HotelDiscoveryFailed

# app/core/app_factory.py -> repository root is two levels up from `app/`
WEB_DIST = Path(__file__).resolve().parent.parent.parent / "web" / "dist"


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(title="Hotel Booking AI Agent")

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
    async def approval_required_handler(request: Request, exc: ApprovalRequiredError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(HotelDiscoveryFailed)
    async def hotel_discovery_failed_handler(request: Request, exc: HotelDiscoveryFailed) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.middleware("http")
    async def error_translation(request: Request, call_next):
        try:
            return await call_next(request)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

    @app.middleware("http")
    async def idempotency_middleware(request: Request, call_next):
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
                resp_body = b""
                async for chunk in resp.body_iterator:
                    resp_body += chunk
                try:
                    payload = __import__("json").loads(resp_body.decode("utf-8") or "{}")
                except Exception:
                    payload = {"raw": resp_body.decode("utf-8", errors="replace")}

                complete_idempotency(
                    db,
                    key=key,
                    route=request.url.path,
                    response_json=payload,
                    succeeded=resp.status_code < 500,
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

    _assets = WEB_DIST / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets), name="ui_assets")

    @app.get("/", response_model=None)
    def spa_index() -> FileResponse | JSONResponse:
        index = WEB_DIST / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(
            {
                "detail": "Web UI not built yet. Run: cd web && npm install && npm run build — then reload, or use /docs for the API.",
            },
            status_code=404,
        )

    return app
