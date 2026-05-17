from __future__ import annotations

import logging
import time

from app.application.messaging.user_copy import chunk_text_for_outbound
from app.core.config import settings
from app.domain.ports import ChannelMessagingPort
from app.infrastructure.telephony.linq_partner import LinqPartnerClient

logger = logging.getLogger(__name__)


class LinqChannelMessagingAdapter:
    """ChannelMessagingPort over Linq Partner API."""

    def __init__(self, client: LinqPartnerClient | None = None) -> None:
        self._client = client or LinqPartnerClient()

    def send_text(
        self,
        to_e164: str,
        message: str,
        *,
        chat_id: str | None = None,
        preferred_service: str | None = None,
    ) -> None:
        if not to_e164:
            return
        if not self._client.is_configured() or not settings.linq_from_number:
            logger.warning(
                "Linq reply NOT sent — set LINQ_API_KEY and LINQ_FROM_NUMBER. Would have sent: %s",
                message[:120],
            )
            return
        # SMS segments are safest under ~320 chars; iMessage tolerates longer bodies.
        if preferred_service and preferred_service.upper() == "SMS":
            max_c = min(320, max(160, int(settings.linq_outbound_chunk_chars)))
        else:
            max_c = max(400, int(settings.linq_outbound_chunk_chars))
        parts = chunk_text_for_outbound(message, max_c)
        delay = float(settings.linq_outbound_chunk_delay_s)
        try:
            for i, part in enumerate(parts):
                head = f"[{i + 1}/{len(parts)}]\n" if len(parts) > 1 else ""
                payload = (head + part)[:8000]
                if chat_id:
                    resp = self._client.send_message_in_chat(
                        chat_id=chat_id,
                        text=payload,
                        preferred_service=preferred_service,
                    )
                else:
                    resp = self._client.send_text_message(to_e164=to_e164, text=payload)
                if resp.status_code >= 400:
                    logger.warning(
                        "Linq send failed %s %s (part %s/%s): %s",
                        resp.status_code,
                        getattr(resp.request, "url", ""),
                        i + 1,
                        len(parts),
                        (resp.text or "")[:500],
                    )
                elif len(parts) > 1:
                    logger.info(
                        "Linq sent chunk %s/%s (%s chars)",
                        i + 1,
                        len(parts),
                        len(payload),
                    )
                if i < len(parts) - 1 and delay > 0:
                    time.sleep(delay)
        except Exception as e:  # noqa: BLE001
            logger.warning("Linq send error: %s", e)
