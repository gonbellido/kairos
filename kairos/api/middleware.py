import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_401_UNAUTHORIZED

from kairos.config import get_settings
from kairos.engine.i18n import set_current_lang, SUPPORTED_LANGS, DEFAULT_LANG

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


class I18nMiddleware(BaseHTTPMiddleware):
    """Detects and sets the locale for the current request."""

    async def dispatch(self, request: Request, call_next):
        lang = self._detect_lang(request)
        set_current_lang(lang)

        # Also store it in request state for easy access in routes
        request.state.lang = lang

        response = await call_next(request)

        # Optionally set a cookie to persist the choice if it came from query param
        if "lang" in request.query_params:
            response.set_cookie("kairos_lang", lang, max_age=86400 * 30, httponly=True)

        return response

    def _detect_lang(self, request: Request) -> str:
        # 1. Query Param
        qp = request.query_params.get("lang")
        if qp in SUPPORTED_LANGS:
            return qp

        # 2. Cookie
        cookie = request.cookies.get("kairos_lang")
        if cookie in SUPPORTED_LANGS:
            return cookie

        # 3. Accept-Language Header
        accept_lang = request.headers.get("Accept-Language", "")
        if accept_lang:
            # Basic parsing: 'en-US,en;q=0.9,es;q=0.8' -> ['en-US', 'en', 'es']
            parts = [p.split(";")[0].split("-")[0].strip().lower() for p in accept_lang.split(",")]
            for p in parts:
                if p in SUPPORTED_LANGS:
                    return p

        return DEFAULT_LANG
