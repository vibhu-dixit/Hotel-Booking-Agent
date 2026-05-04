from __future__ import annotations

from fastapi import APIRouter

from app.api.routers import ai_gateway, bookings, calls, decisions, hotels, linq_webhooks, payment_checkout, trips

api_router = APIRouter(tags=["api"])
api_router.include_router(trips.router)
api_router.include_router(hotels.router)
api_router.include_router(calls.router)
api_router.include_router(decisions.router)
api_router.include_router(bookings.router)
api_router.include_router(ai_gateway.router)
api_router.include_router(linq_webhooks.router)
api_router.include_router(payment_checkout.router)
