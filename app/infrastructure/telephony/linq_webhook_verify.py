from __future__ import annotations

import hmac
import hashlib

from app.core.config import settings


def verify_linq_webhook_signature(*, raw_body: bytes, timestamp: str | None, signature: str | None) -> bool:
    """HMAC-SHA256 over '{timestamp}.{raw_body}' per Linq docs."""
    secret = settings.linq_webhook_secret
    if not secret:
        return True
    if not timestamp or not signature:
        return False
    message = f"{timestamp}.{raw_body.decode('utf-8')}"
    expected = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
