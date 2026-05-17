import asyncio
import logging
import time
from typing import Any

from langgraph.graph import StateGraph, END, START
from qdrant_client import QdrantClient

from kairos.core.state import AgentState
from kairos.engine.journey_engine import JourneyEngine
from kairos.core.exceptions import KairosError
from kairos.engine.profile_engine import ProfileEngine
from kairos.engine.prompt_engine import PromptEngine
from kairos.engine.state_classifier import StateClassifier
from kairos.engine.knowledge_retriever import KnowledgeRetriever
from kairos.engine.imprint_mapper import ImprintMapper
from kairos.engine.pattern_generator import PatternGenerator
from kairos.engine.pattern_miner import PatternMiner
from kairos.engine.client_synthesizer import ClientSynthesizer
from kairos.engine.feedback_processor import FeedbackProcessor
from kairos.engine.impronta_learner import ImprontaLearner
from kairos.engine.notification_service import NotificationService
from kairos.engine.session_manager import SessionManager
from kairos.engine.audio.transcriber import AudioTranscriber
from kairos.engine.obsidian.writer import ObsidianWriter
from kairos.memory.stores import (
    RawStore, CaseStore, PatternStore, ExecutionStore, KnowledgeStore, ClientStore,
)
from kairos.memory.embeddings import OpenAIEmbeddingProvider, LocalEmbeddingProvider, GoogleEmbeddingProvider, GoogleMultimodalEmbeddingProvider
from kairos.memory.scoring import ScoringEngine
from kairos.config import get_settings
from kairos.config.llm_factory import create_llm, create_eval_llm
from kairos.config.trace import TraceContext
from kairos.engine.metrics import get_metrics
from kairos.plugins.loader import PluginLoader

from .nodes import (
    audio_ingestion_node, perception_node, retrieve_node, score_node, aggregate_node,
    analyst_node, worker_node, response_validator, experience_updater,
    client_synthesizer_node, alert_checker_node, impronta_learning_node,
    obsidian_connector_node, supervisor_node,
)
from .nodes.journey_agent import journey_inject_node, journey_advance_node

logger = logging.getLogger(__name__)


class KairosRuntime:
    def __init__(self, profiles_dir: str = "./profiles", prompt_store=None, journey_engine: JourneyEngine = None):
        settings = get_settings()

        self.qdrant = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key or None,
            check_compatibility=False,
        )
        self.embeddings = self._resolve_embeddings(settings)
        self.llm = create_llm()
        self.eval_llm = create_eval_llm()

        self.raw_store = RawStore(self.qdrant, self.embeddings)
        self.case_store = CaseStore(self.qdrant, self.embeddings)
        self.pattern_store = PatternStore(self.qdrant, self.embeddings)
        self.execution_store = ExecutionStore(self.qdrant, self.embeddings)
        self.knowledge_store = KnowledgeStore(self.qdrant, self.embeddings)
        self.client_store = ClientStore(self.qdrant, self.embeddings)

        self._metrics = get_metrics()
        self._metrics.set_embedding_provider((settings.embedding_provider or "openai").lower())

        # D4: Plugin system
        self.plugin_loader = PluginLoader()

        # Prompt management
        self.prompt_store = prompt_store

        self.profile_engine = ProfileEngine(profiles_dir)
        self.prompt_engine = PromptEngine()
        # B1: StateClassifier con LLM fallback para clasificaciones de baja confianza
        self.classifier = StateClassifier(
            llm=self.llm,
            confidence_threshold=settings.classifier_confidence_threshold,
        )
        self.knowledge_retriever = KnowledgeRetriever(self.knowledge_store)
        self.scoring_engine = ScoringEngine()
        self.imprint_mapper = ImprintMapper()
        self.pattern_generator = PatternGenerator()
        # B2: PatternMiner para auto-mining desde experience_updater
        self.pattern_miner = PatternMiner(self.case_store, self.pattern_store)
        self._session_counters: dict[str, int] = {}
        self._pattern_mine_every = settings.pattern_mine_every

        self.client_synthesizer = ClientSynthesizer(self.eval_llm)

        vault_path = settings.obsidian_vault or ""
        self._vault_path = vault_path
        self.obsidian = ObsidianWriter(vault_path) if vault_path else None
        self.feedback_processor = FeedbackProcessor(self.case_store, self.scoring_engine)
        self.impronta_learner = ImprontaLearner(self.case_store, self.profile_engine)
        self.notifier = NotificationService()
        self.session_manager = SessionManager()
        self.journey_engine = journey_engine
        self.transcriber = AudioTranscriber()

        self._ensure_collections()

    @staticmethod
    def _resolve_embeddings(settings):
        provider = (settings.embedding_provider or "openai").lower()

        # Auto-detect Google cuando el modelo es Gemini aunque EMBEDDING_PROVIDER no esté explícito
        if provider == "openai" and "gemini" in (settings.embedding_model or "").lower():
            provider = "google"
            logger.info("EMBEDDING_PROVIDER=google detectado por EMBEDDING_MODEL=%s", settings.embedding_model)

        if provider in ("google", "gemini", "google_multimodal"):
            key = settings.google_api_key or settings.embedding_api_key
            if not key:
                raise RuntimeError(
                    "GOOGLE_API_KEY requerida para embeddings Google. "
                    "Configura GOOGLE_API_KEY en .env o cambia EMBEDDING_PROVIDER=openai."
                )
            try:
                emb = GoogleMultimodalEmbeddingProvider(api_key=key)
                if emb._client:
                    logger.info("Embeddings: Gemini multimodal %s (%dd)", emb._model_name, emb.dimensions)
                    return emb
            except Exception:
                pass
            emb = GoogleEmbeddingProvider(api_key=key)
            if not emb._client:
                raise RuntimeError(
                    "Google embeddings falló al inicializar. "
                    "Instala: pip install langchain-google-genai google-genai"
                )
            logger.info("Embeddings: Google Gemini %s (%dd)", emb._model_name, emb.dimensions)
            return emb

        if provider == "local":
            emb = LocalEmbeddingProvider()
            logger.info("Embeddings: local %s (%dd)", emb._model_name, emb.dimensions)
            return emb

        # OpenAI (default)
        if not settings.embedding_api_key:
            logger.warning(
                "EMBEDDING_API_KEY no configurada. Usando embeddings locales (sentence-transformers). "
                "La búsqueda semántica será menos precisa."
            )
            emb = LocalEmbeddingProvider()
            logger.info("Embeddings: local %s (%dd)", emb._model_name, emb.dimensions)
            return emb

        emb = OpenAIEmbeddingProvider()
        logger.info("Embeddings: OpenAI %s (%dd)", emb._model, emb.dimensions)
        return emb

    def _ensure_collections(self):
        for store in [
            self.raw_store, self.case_store, self.pattern_store,
            self.execution_store, self.knowledge_store,
        ]:
            try:
                store.ensure_collection()
            except Exception as e:
                logger.warning("Collection init skipped for %s: %s", type(store).__name__, e)
                continue
        try:
            self.client_store.ensure_collections()
        except Exception as e:
            logger.warning("Client store init skipped: %s", e)

    async def startup_purge(self) -> None:
        """B3: Purga TTL en segundo plano al arrancar el sistema."""
        settings = get_settings()
        try:
            if settings.memory_ttl_raw_days > 0:
                loop = asyncio.get_event_loop()
                n = await loop.run_in_executor(
                    None, lambda: self.raw_store.purge_expired(settings.memory_ttl_raw_days)
                )
                if n:
                    logger.info("TTL purge: %d raw memories eliminadas (>%dd)", n, settings.memory_ttl_raw_days)
            if settings.memory_ttl_execution_days > 0:
                loop = asyncio.get_event_loop()
                n = await loop.run_in_executor(
                    None, lambda: self.execution_store.purge_expired(settings.memory_ttl_execution_days)
                )
                if n:
                    logger.info("TTL purge: %d executions eliminadas (>%dd)", n, settings.memory_ttl_execution_days)
        except Exception as e:
            logger.warning("TTL purge falló (no crítico): %s", e)

    async def _notify_node_async(self, state: AgentState) -> dict:
        client_id = state.get("context", {}).get("client_id", "")
        alerts_triggered = state.get("decisions", [])
        alert_count = sum(1 for d in alerts_triggered if d.get("agent") == "alert_checker")

        if alert_count > 0 and client_id:
            alerts = state.get("alerts", [])
            for alert in alerts:
                await self.notifier.send_alert(alert)

        return {"next_agent": "obsidian"}

    def _timed(self, name: str, fn):
        """C2: envuelve un nodo con medición de latencia."""

        async def wrapped(state):
            t0 = time.perf_counter()
            result = await fn(state)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self._metrics.record_node_latency(name, elapsed_ms)
            return result

        return wrapped

    # ── D1: conditional routing functions ──
    @staticmethod
    def _has_audio(state: AgentState) -> bool:
        ctx = state.get("context", {})
        return bool(ctx.get("_audio_bytes") or ctx.get("_audio_path"))

    @staticmethod
    def _has_client(state: AgentState) -> bool:
        return bool(state.get("context", {}).get("client_id", ""))

    def _has_obsidian(self, state: AgentState) -> bool:
        _ = state
        return self.obsidian is not None

    def _build_graph(self) -> StateGraph:
        builder = StateGraph(AgentState)

        async def _sup(s): return await supervisor_node(s, self.llm, self.prompt_store)
        async def _aud(s): return await audio_ingestion_node(s, self.transcriber, self.raw_store)
        async def _per(s): return await perception_node(s, self.classifier, self.prompt_store)
        async def _ret(s): return await retrieve_node(s, self.raw_store, self.case_store, self.pattern_store, self.knowledge_retriever, self._metrics)
        async def _sco(s): return await score_node(s, self.scoring_engine, self.profile_engine, self._metrics)
        async def _agg(s): return await aggregate_node(s, self.pattern_generator, self.imprint_mapper)
        # D2: analyst usa eval_llm en vez de crear uno nuevo
        async def _ana(s): return await analyst_node(s, self.client_store, self.eval_llm, self.prompt_store)
        async def _wrk(s): return await worker_node(s, self.profile_engine, self.prompt_engine, self.case_store, self.execution_store, self.llm, self.plugin_loader)
        async def _val(s): return await response_validator(s, self.eval_llm, self.plugin_loader, self.prompt_store)
        async def _lrn(s):
            result = await experience_updater(s, self.case_store, self.pattern_store, self.execution_store)
            profile_id = s.get("profile_id", "")
            if profile_id and self._pattern_mine_every > 0:
                cnt = self._session_counters.get(profile_id, 0) + 1
                self._session_counters[profile_id] = cnt
                if cnt % self._pattern_mine_every == 0:
                    asyncio.ensure_future(self.pattern_miner.mine(profile_id))
                    logger.info("Auto-mining patterns para %s (sesión #%d)", profile_id, cnt)
            return result
        async def _csy(s): return await client_synthesizer_node(s, self.client_store, self.client_synthesizer)
        async def _alc(s): return await alert_checker_node(s, self.client_store)
        async def _ipl(s): return await impronta_learning_node(s, self.impronta_learner)
        async def _ntf(s): return await self._notify_node_async(s)
        async def _obs(s): return await obsidian_connector_node(s, self.obsidian, self.client_store)
        async def _jin(s): return await journey_inject_node(s, self.journey_engine)
        async def _jad(s): return await journey_advance_node(s, self.journey_engine)

        builder.add_node("supervisor", self._timed("supervisor", _sup))
        builder.add_node("audio", self._timed("audio", _aud))
        builder.add_node("perception", self._timed("perception", _per))
        builder.add_node("retrieve", self._timed("retrieve", _ret))
        builder.add_node("score", self._timed("score", _sco))
        builder.add_node("aggregate", self._timed("aggregate", _agg))
        builder.add_node("analyst", self._timed("analyst", _ana))
        builder.add_node("worker", self._timed("worker", _wrk))
        builder.add_node("validate", self._timed("validate", _val))
        builder.add_node("learn", self._timed("learn", _lrn))
        builder.add_node("client_synth", self._timed("client_synth", _csy))
        builder.add_node("alert_check", self._timed("alert_check", _alc))
        builder.add_node("impronta_learn", self._timed("impronta_learn", _ipl))
        builder.add_node("notify", self._timed("notify", _ntf))
        builder.add_node("obsidian", self._timed("obsidian", _obs))
        builder.add_node("journey_inject", self._timed("journey_inject", _jin))
        builder.add_node("journey_advance", self._timed("journey_advance", _jad))

        # D1: Conditional branching — nodos opcionales
        builder.add_edge(START, "supervisor")

        # Audio: solo si hay datos de audio en el contexto
        builder.add_conditional_edges(
            "supervisor",
            lambda s: "audio" if self._has_audio(s) else "perception",
            {"audio": "audio", "perception": "perception"},
        )
        builder.add_edge("audio", "perception")

        # Pipeline principal (siempre se ejecuta)
        builder.add_edge("perception", "retrieve")
        builder.add_edge("retrieve", "score")
        builder.add_edge("score", "aggregate")

        # Analyst: solo si hay client_id asignado (~30% de requests)
        builder.add_conditional_edges(
            "aggregate",
            lambda s: "analyst" if self._has_client(s) else "journey_inject",
            {"analyst": "analyst", "journey_inject": "journey_inject"},
        )
        builder.add_edge("analyst", "journey_inject")
        builder.add_edge("journey_inject", "worker")

        builder.add_edge("worker", "validate")
        builder.add_edge("validate", "journey_advance")
        builder.add_edge("journey_advance", "learn")
        builder.add_edge("learn", "client_synth")
        builder.add_edge("client_synth", "alert_check")
        builder.add_edge("alert_check", "impronta_learn")
        builder.add_edge("impronta_learn", "notify")

        # Obsidian: solo si OBSIDIAN_VAULT está configurado
        builder.add_conditional_edges(
            "notify",
            lambda s: "obsidian" if self._has_obsidian(s) else END,
            {"obsidian": "obsidian", "__end__": END},
        )
        builder.add_edge("obsidian", END)

        return builder.compile()

    async def run(
        self,
        session_id: str,
        profile_id: str,
        message: str,
        user_id: str = "default",
        context: dict | None = None,
    ) -> dict[str, Any]:
        graph = self._build_graph()
        initial: AgentState = {
            "session_id": session_id,
            "profile_id": profile_id,
            "user_id": user_id,
            "message": message,
            "context": context or {},
            "next_agent": "perception",
        }

        # Cambio 1: Detectar journey activo en el orchestrator
        client_id = (context or {}).get("client_id")
        if self.journey_engine and client_id:
            journey_context = await self.journey_engine.get_client_journey(client_id)
            if journey_context and journey_context.get("status") not in ("completed", "not_started", None):
                initial["journey_context"] = journey_context
        # C1: propagar trace context al pipeline
        with TraceContext(
            session_id=session_id,
            profile_id=profile_id,
            coach_id=user_id,
        ):  # trace_id ya viene del middleware
            try:
                self._metrics.record_request()
                result = await graph.ainvoke(initial)
                if self._metrics._total_requests % 50 == 0:
                    self._metrics.log_summary()
                # D4: fire on_session_end hooks
                profile_id = result.get("profile_id", "")
                if profile_id:
                    try:
                        await self.plugin_loader.run_hook(
                            profile_id, "on_session_end",
                            session_id,
                            {"session_id": session_id, "profile_id": profile_id},
                        )
                    except Exception:
                        pass
                return result
            except KairosError as e:
                logger.error("Kairos runtime error: %s", e)
                return {"final_response": f"System error: {e}", "confidence": 0.0, "errors": [str(e)]}

    async def close(self):
        self.qdrant.close()


def build_kairos_graph(profiles_dir: str = "./profiles") -> KairosRuntime:
    return KairosRuntime(profiles_dir)
