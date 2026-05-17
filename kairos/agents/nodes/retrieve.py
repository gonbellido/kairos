import logging
from datetime import datetime, timezone
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
from kairos.core.state import AgentState, Decision
from kairos.memory.stores import RawStore, CaseStore, PatternStore, KnowledgeStore
from kairos.engine.knowledge_retriever import KnowledgeRetriever

logger = logging.getLogger(__name__)

# D3: perfiles "hermanos" para cross-profile memory sharing
CROSS_PROFILES = {
    "coaching": ["comercial"],
    "comercial": ["coaching"],
    "financiero": ["coaching", "comercial"],
}

CROSS_TOP_K = 3  # cuántos casos extraer de cada perfil hermano


async def retrieve_node(
    state: AgentState,
    raw_store: RawStore,
    case_store: CaseStore,
    pattern_store: PatternStore,
    knowledge_retriever: KnowledgeRetriever,
    metrics=None,
) -> dict[str, Any]:
    profile_id = state["profile_id"]
    message = state["message"]
    client_id = state.get("context", {}).get("client_id", "")
    cross_profile = state.get("context", {}).get("cross_profile", True)

    # Memoria global del coach (disponible para todos los clientes)
    coach_raw = await raw_store.search(message, profile_id, client_id="", top_k=10)
    coach_cases = await case_store.semantic_search(message, profile_id, client_id="", top_k=10)

    memories_raw = list(coach_raw)
    raw_cases = list(coach_cases)

    # Memoria específica del cliente (si aplica)
    if client_id:
        client_raw = await raw_store.search(message, profile_id, client_id=client_id, top_k=10)
        client_cases = await case_store.semantic_search(message, profile_id, client_id=client_id, top_k=10)
        memories_raw.extend(client_raw)
        raw_cases.extend(client_cases)

    # D3: Cross-profile memory sharing — casos de perfiles hermanos
    cross_count = 0
    if cross_profile and profile_id in CROSS_PROFILES:
        for sibling in CROSS_PROFILES[profile_id]:
            try:
                sibling_cases = await case_store.semantic_search(
                    message, sibling, client_id="", top_k=CROSS_TOP_K
                )
                raw_cases.extend(sibling_cases)
                cross_count += len(list(sibling_cases))
            except Exception:
                pass
        if cross_count:
            logger.debug("Cross-profile: %d cases from %s for profile %s",
                         cross_count, CROSS_PROFILES[profile_id], profile_id)

    patterns = await pattern_store.search(message, profile_id)
    knowledge = await knowledge_retriever.retrieve(message, profile_id)

    if metrics:
        if memories_raw:
            metrics.record_hit("N1_raw", len(memories_raw))
        if raw_cases:
            metrics.record_hit("N2_cases", len(raw_cases))
        if patterns:
            metrics.record_hit("N3_patterns", len(patterns))

    decision: Decision = {
        "agent": "retrieve",
        "action": "retrieve",
        "reasoning": f"Retrieved {len(raw_cases)} cases ({cross_count} cross-profile), {len(patterns)} patterns, {len(knowledge)} docs",
        "timestamp": _utcnow().isoformat(),
        "data_snapshot": {
            "case_count": len(raw_cases),
            "cross_profile_count": cross_count,
            "pattern_count": len(patterns),
            "knowledge_count": len(knowledge),
        },
    }

    return {
        "raw_memories": memories_raw,
        "retrieved_cases": raw_cases,
        "patterns": patterns,
        "knowledge_docs": knowledge,
        "decisions": [decision],
        "next_agent": "score",
    }
