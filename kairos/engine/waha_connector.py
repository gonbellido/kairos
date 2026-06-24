"""F8: WAHA Connector — REST client for WhatsApp HTTP API."""

import logging

import httpx

logger = logging.getLogger(__name__)


class WAHAClient:
    def __init__(self, base_url: str = "http://waha:3000", api_key: str = ""):
        self._base = base_url.rstrip("/")
        self._headers = {"X-Api-Key": api_key, "Content-Type": "application/json"} if api_key else {}

    async def send_text(self, session: str, chat_id: str, text: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"{self._base}/api/sendText",
                    json={
                        "session": session,
                        "chatId": chat_id,
                        "text": text,
                    },
                    headers=self._headers,
                )
                ok = r.is_success
                if not ok:
                    logger.warning("WAHA sendText failed: %s %s", r.status_code, r.text[:200])
                return ok
        except Exception as e:
            logger.warning("WAHA sendText error: %s", e)
            return False
