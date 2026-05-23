import logging
import httpx
from datetime import datetime, timezone
from typing import Any

from kairos.core.client import Alert

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, webhook_url: str | None = None):
        self._webhook = webhook_url

    async def send_alert(self, alert: Alert, locale: str = "es") -> bool:
        logger.info("ALERT [%s] %s: %s", alert.nivel, alert.tipo, alert.mensaje)

        if not self._webhook:
            return False

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self._webhook, json={
                    "event": "kairos.alert",
                    "tipo": alert.tipo,
                    "nivel": alert.nivel,
                    "mensaje": alert.mensaje,
                    "cliente_id": alert.cliente_id,
                    "accion": alert.accion,
                    "locale": locale,
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                })
                resp.raise_for_status()
                logger.info("Webhook delivered: %s", resp.status_code)
                return True
        except Exception as e:
            logger.warning("Webhook failed: %s", e)
            return False

    async def send_summary(self, coach_id: str, summary: dict[str, Any], locale: str = "es") -> bool:
        logger.info("SUMMARY for %s: %s", coach_id, summary)
        if not self._webhook:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self._webhook, json={
                    "event": "kairos.summary",
                    "coach_id": coach_id,
                    **summary,
                    "locale": locale,
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                })
                return resp.status_code == 200
        except Exception:
            return False
