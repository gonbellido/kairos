import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from kairos.config import get_settings
from kairos.config.trace import TraceContext, generate_trace_id
from kairos.config.logging import setup_logging as setup_structured_logging
from kairos.config.json_logging import setup_json_logging
from kairos.agents.orchestrator import KairosRuntime
from kairos.engine.telegram_bot import KairosTelegramBot
from kairos.engine.health_checker import HealthChecker
from kairos.engine.coach_auth_pg import CoachDBA
from kairos.engine.metrics import get_metrics
from kairos.engine.cache import get_cache_stats
from kairos.engine.i18n import get_i18n
from kairos.engine.prompt_store import PromptStore
from kairos.engine.journey_engine import JourneyEngine
from kairos.api.middleware import AuthMiddleware
from kairos.api.rate_limiter import RateLimiter
from kairos.db.session import create_session_factory
from .routes import chat, stream, clients, feedback, sessions, upload, materials, coach_assist, web, monitor, voice, journey_test
from .routes import settings as settings_routes
from . import architect as architect_routes

logger = logging.getLogger(__name__)

_bot_app = None


class TraceMiddleware(BaseHTTPMiddleware):
    """C1: Genera trace_id por request y lo propaga al contexto de logging."""

    async def dispatch(self, request: Request, call_next):
        trace_id = generate_trace_id()
        with TraceContext(trace_id=trace_id):
            response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id
            return response


class LanguageMiddleware(BaseHTTPMiddleware):
    """E: Detecta idioma del request y configura i18n."""

    async def dispatch(self, request: Request, call_next):
        qp = request.query_params.get("lang", "")
        cookie = request.cookies.get("kairos_lang", "")
        lang = qp if qp in ("es", "en") else (cookie if cookie in ("es", "en") else "es")
        get_i18n(lang)
        response = await call_next(request)
        if not qp and not cookie:
            response.set_cookie("kairos_lang", lang, max_age=86400 * 30, httponly=True)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bot_app
    app_settings = get_settings()

    if app_settings.log_level.upper() == "JSON":
        setup_json_logging("INFO")
    else:
        setup_structured_logging(app_settings.log_level)

    # C3: CoachDB en PostgreSQL
    session_factory = create_session_factory()
    coach_db = CoachDBA(session_factory)
    app.state.coach_db = coach_db
    try:
        await coach_db.seed_defaults()
    except Exception as e:
        logger.error("Failed to seed coaches: %s", e)

    # Prompt management
    prompt_store = PromptStore(session_factory)
    app.state.prompt_store = prompt_store
    try:
        await prompt_store.seed_defaults()
    except Exception as e:
        logger.error("Failed to seed prompts: %s", e)

    # Fase I: Journey system — siempre activo
    journey_engine = JourneyEngine(session_factory)
    app.state.journey_engine = journey_engine
    app.state._session_factory = session_factory
    try:
        await journey_engine.seed_defaults()
    except Exception as e:
        logger.error("Failed to seed journeys: %s", e)
    logger.info("Journey engine initialized with %d templates", 
                len(await journey_engine.list_journeys("default")))

    runtime = KairosRuntime(profiles_dir=app_settings.profiles_dir, prompt_store=prompt_store, journey_engine=journey_engine)
    journey_engine._case_store = runtime.case_store
    app.state.runtime = runtime
    app.state.health_checker = HealthChecker(runtime.qdrant, runtime.llm, runtime.embeddings)
    asyncio.create_task(runtime.startup_purge())

    # Fase L: Deep graph compiled once at startup (Etapa 5)
    try:
        from kairos.paths.deep_path import get_deep_graph
        app.state.deep_graph = get_deep_graph()
        logger.info("Deep graph (LangGraph) compiled at startup")
    except Exception as e:
        logger.warning("Deep graph compilation skipped: %s", e)

    # G4.2: Telegram bots multi-coach
    app.state.telegram_bots = {}
    coaches = await coach_db.list_coaches()
    for c in coaches:
        token = c.get("telegram_token", "")
        if token:
            try:
                bot = KairosTelegramBot(
                    token=token, runtime=runtime,
                    coach_id=c["id"], lang=c.get("language", "es"),
                    journey_engine=app.state.journey_engine,
                )
                _bot_app_inner = bot.build_app()
                app.state.telegram_bots[c["id"]] = bot
                logger.info("Telegram bot ready for coach %s (%s)", c["name"], c["id"])
            except Exception as e:
                logger.warning("Failed to init Telegram bot for %s: %s", c["id"], e)

    # Legacy global bot
    if app_settings.telegram_token:
        bot = KairosTelegramBot(token=app_settings.telegram_token, runtime=runtime)
        _bot_app = bot.build_app()
        app.state.telegram_bot_app = _bot_app
        app.state.telegram_bot = bot
        logger.info("Global Telegram bot configured")

        original = runtime.notifier.send_alert
        async def notify_with_tg(alert):
            await original(alert)
            if app_settings.telegram_chat_id:
                await bot.send_alert(app_settings.telegram_chat_id, f"{alert.mensaje}", alert.nivel)
        runtime.notifier.send_alert = notify_with_tg
        runtime.notifier._bot = bot
    else:
        logger.info("Telegram: set TELEGRAM_TOKEN in .env or per-coach in admin panel")

    logger.info("KAIROS system initialized")
    yield
    if _bot_app:
        await _bot_app.stop()
    await runtime.close()
    logger.info("KAIROS shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(title="KAIROS API", version="0.1.0", lifespan=lifespan)

    app_settings = get_settings()

    app.add_middleware(CORSMiddleware, allow_origins=app_settings.api_cors_origins.split(","),
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(LanguageMiddleware)
    app.add_middleware(TraceMiddleware)
    if app_settings.llm_api_key:
        app.add_middleware(AuthMiddleware)
    app.add_middleware(RateLimiter)

    @app.get("/health")
    async def health(req: Request):
        checker = req.app.state.health_checker
        result = checker.check()
        status = 200 if result["status"] == "ok" else 503
        return Response(status_code=status, content=json.dumps(result, default=str), media_type="application/json")

    # C2: endpoint de métricas del pipeline
    @app.get("/metrics")
    async def metrics(req: Request):
        m = get_metrics()
        snap = m.snapshot()
        snap["cache"] = get_cache_stats()
        # D5: Prometheus text format support
        fmt = req.query_params.get("format", "json")
        if fmt == "prometheus":
            return Response(
                content=_to_prometheus(snap),
                media_type="text/plain; version=0.0.4",
            )
        return snap

    @app.post("/telegram/webhook")
    async def telegram_webhook(req: Request):
        from telegram import Update
        bot_app = getattr(req.app.state, "telegram_bot_app", None)
        if bot_app:
            data = await req.json()
            update = Update.de_json(data, bot_app.bot)
            await bot_app.process_update(update)
            return {"ok": True}
        return {"ok": False, "detail": "Bot not configured"}

    @app.post("/telegram/webhook/{coach_id}")
    async def telegram_webhook_coach(req: Request, coach_id: str):
        from telegram import Update
        bots = getattr(req.app.state, "telegram_bots", {})

        # Lazy init: create bot on first webhook if not in memory
        if coach_id not in bots:
            try:
                coach = await req.app.state.coach_db.get_by_id(coach_id)
                if coach and coach.get("telegram_token"):
                    from kairos.engine.telegram_bot import KairosTelegramBot
                    bot = KairosTelegramBot(
                        token=coach["telegram_token"], runtime=req.app.state.runtime,
                        coach_id=coach_id, lang=coach.get("language", "es"),
                        journey_engine=getattr(req.app.state, "journey_engine", None),
                    )
                    bot.build_app()
                    await bot._app.initialize()
                    bots[coach_id] = bot
                    req.app.state.telegram_bots = bots
            except Exception as e:
                return {"ok": False, "detail": str(e)}

        bot = bots.get(coach_id)
        if bot and bot._app:
            try:
                data = await req.json()
                update = Update.de_json(data, bot._app.bot)
                await bot._app.process_update(update)
                return {"ok": True}
            except Exception as e:
                return {"ok": False, "detail": str(e)}
        return {"ok": False, "detail": f"Bot for coach {coach_id} not active"}

    app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
    app.include_router(stream.router, prefix="/api/v1", tags=["chat"])
    app.include_router(clients.router, prefix="/api/v1")
    app.include_router(feedback.router, prefix="/api/v1")
    app.include_router(sessions.router, prefix="/api/v1")
    app.include_router(upload.router, prefix="/api/v1")
    app.include_router(materials.router, prefix="/api/v1")
    app.include_router(coach_assist.router, prefix="/api/v1")
    app.include_router(web.router)
    app.include_router(settings_routes.router, prefix="/api/v1")
    app.include_router(monitor.router)
    app.include_router(voice.router, prefix="/api/v1")
    app.include_router(architect_routes.router)
    app.include_router(journey_test.router)

    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    static_dir = Path(__file__).parent.parent / "web" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def root():
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/coach")

    logger.info("KAIROS routes: %d", len([r for r in app.routes if hasattr(r, 'path')]))
    return app


def _to_prometheus(snap: dict) -> str:
    """D5: Convert metrics snapshot to Prometheus text format."""
    lines = []

    lines.append(f'# HELP kairos_requests_total Total pipeline requests')
    lines.append(f'# TYPE kairos_requests_total counter')
    lines.append(f'kairos_requests_total {snap.get("total_requests", 0)}')

    # Node latencies
    for node, stats in sorted(snap.get("nodes", {}).items()):
        name = f'kairos_node_latency_ms{{node="{node}"}}'
        lines.append(f'# HELP kairos_node_latency_ms Latency per pipeline node')
        lines.append(f'# TYPE kairos_node_latency_ms summary')
        lines.append(f'kairos_node_latency_ms_count{{node="{node}"}} {stats["count"]}')
        lines.append(f'kairos_node_latency_ms_avg{{node="{node}"}} {stats["avg_ms"]}')
        lines.append(f'kairos_node_latency_ms_p50{{node="{node}"}} {stats["p50_ms"]}')
        lines.append(f'kairos_node_latency_ms_p95{{node="{node}"}} {stats["p95_ms"]}')
        lines.append(f'kairos_node_latency_ms_p99{{node="{node}"}} {stats["p99_ms"]}')

    # Embedding provider
    lines.append(f'# HELP kairos_embedding_provider Active embedding provider')
    lines.append(f'# TYPE kairos_embedding_provider gauge')
    lines.append(f'kairos_embedding_provider{{provider="{snap.get("embedding_provider", "unknown")}"}} 1')

    # Cache stats
    cache = snap.get("cache", {})
    lines.append(f'# HELP kairos_cache_size Cache entry count')
    lines.append(f'# TYPE kairos_cache_size gauge')
    lines.append(f'kairos_cache_size{{cache="embeddings"}} {cache.get("embedding_cache_size", 0)}')
    lines.append(f'kairos_cache_size{{cache="llm"}} {cache.get("llm_cache_size", 0)}')

    return "\n".join(lines) + "\n"


app = create_app()
