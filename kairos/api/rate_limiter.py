import logging
import time
from collections import defaultdict
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from kairos.config import get_settings

logger = logging.getLogger(__name__)

# Default limits per plan
PLAN_LIMITS = {"free": 60, "pro": 300, "admin": 500}


class RateLimiter(BaseHTTPMiddleware):
    """C4: Rate limiting por coach_id con límites diferenciados por plan."""

    def __init__(self, app, max_requests: int | None = None, window_seconds: int | None = None):
        super().__init__(app)
        self._window = window_seconds or 60
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        settings = get_settings()

        # C4: intentar identificar por coach_id (vía cookie de sesión)
        key = self._resolve_key(request, settings)

        now = time.time()
        window_start = now - self._window
        self._buckets[key] = [t for t in self._buckets[key] if t > window_start]

        if len(self._buckets[key]) >= self._limit_for(key, settings):
            return Response(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                content=f'{{"detail":"Rate limit exceeded. Max {self._limit_for(key, settings)} requests per {self._window}s"}}',
                media_type="application/json",
            )

        self._buckets[key].append(now)
        return await call_next(request)

    def _resolve_key(self, request: Request, settings) -> str:
        token = request.cookies.get("kairos_token")
        if token:
            return f"coach:{token}"
        ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"

    def _limit_for(self, key: str, settings) -> int:
        if key.startswith("coach:"):
            return settings.rate_limit_pro  # autenticados: límite pro por defecto
        return settings.rate_limit_free  # no autenticados: límite free
