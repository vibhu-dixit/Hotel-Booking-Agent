from __future__ import annotations

import hmac
import hashlib

from app.core.config import settings


def verify_linq_webhook_signature(*, raw_body: bytes, timestamp: str | None, signature: str | None) -> bool:
    secret = settings.linq_webhook_secret
    if not secret:
        return True
    if not timestamp or not signature:
        return False
    # Linq signs: HMAC-SHA256(secret, "{timestamp}.{raw_body_bytes}")
    signed = timestamp.encode("utf-8") + b"." + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
