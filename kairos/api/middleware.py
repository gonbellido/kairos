import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_401_UNAUTHORIZED

from kairos.config import get_settings

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key: str | None = None):
        super().__init__(app)
        self._api_key = api_key or ""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        expected = self._api_key or settings.llm_api_key

        # Skip auth for health, docs, and web UI
        path = request.url.path
        if path == "/" and not expected:
            return await call_next(request)
        if path in ("/health", "/docs", "/openapi.json", "/redoc", "/", "/favicon.ico", "/login"):
            return await call_next(request)
        if any(path.startswith(p) for p in ["/coach", "/admin", "/login", "/logout", "/static", "/client", "/telegram",
                                              "/api/v1/upload", "/api/v1/materials", "/api/v1/coach",
                                              "/api/v1/chat", "/api/v1/settings", "/api/v1/clients",
                                              "/api/v1/journeys", "/api/v1/architect", "/api/v1/voice"]):
            return await call_next(request)

        if expected:
            provided = request.headers.get("X-API-Key", "")
            if not provided or provided != expected:
                logger.warning("Auth failed for %s", request.url.path)
                return Response(
                    status_code=HTTP_401_UNAUTHORIZED,
                    content='{"detail":"Invalid or missing API Key"}',
                    media_type="application/json",
                )

        return await call_next(request)
