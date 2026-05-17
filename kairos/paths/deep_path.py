"""Etapa 5: Deep path — LangGraph with analyst → retrieve conditional loop.

The ONLY place LangGraph is used. Analyst can decide in runtime that
more context is needed and loop back to retrieve with a refined query.
"""

import asyncio
import logging
from typing import TypedDict

logger = logging.getLogger(__name__)

_deep_graph = None
MAX_RETRIEVE_LOOPS = 2


class DeepState(TypedDict, total=False):
    message: str
    client_id: str
    coach_id: str
    journey_id: str
    session_id: str
    channel: str
    metadata: dict
    fast_response: str
    query_vector: list[float]
    rag_results: list[dict]
    retrieve_count: int
    analysis: str
    analysis_needs_more_context: bool
    refined_query: str
    enriched_response: str
    risk_level: str


def get_deep_graph():
    global _deep_graph
    if _deep_graph is not None:
        return _deep_graph

    from langgraph.graph import StateGraph, END

    graph = StateGraph(DeepState)
    graph.add_node("retrieve", _retrieve_node)
    graph.add_node("analyst", _analyst_node)
    graph.add_node("enrich_worker", _enrich_worker_node)
    graph.add_node("learn", _learn_node)
    graph.add_node("alert_check", _alert_check_node)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "analyst")
    graph.add_conditional_edges(
        "analyst",
        _needs_more_context,
        {"retrieve": "retrieve", "enrich": "enrich_worker"},
    )
    graph.add_edge("enrich_worker", "learn")
    graph.add_edge("learn", "alert_check")
    graph.add_edge("alert_check", END)

    _deep_graph = graph.compile()
    logger.info("Deep graph compiled (LangGraph)")
    return _deep_graph


def _needs_more_context(state: DeepState) -> str:
    if state.get("retrieve_count", 0) >= MAX_RETRIEVE_LOOPS:
        return "enrich"
    if state.get("analysis_needs_more_context", False):
        return "retrieve"
    return "enrich"


# ── Nodes ──

async def _retrieve_node(state: DeepState) -> dict:
    """One embedding reused across all Qdrant searches."""
    from kairos.memory.memory import _embed, _get_qdrant

    message = state.get("refined_query") or state["message"]
    count = state.get("retrieve_count", 0) + 1

    vector = state.get("query_vector")
    if not vector:
        vector = await _embed(message)

    qdrant = _get_qdrant()
    try:
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue

        client_filter = Filter(must=[
            FieldCondition(key="client_id", match=MatchValue(value=state.get("client_id", "")))
        ]) if state.get("client_id") else None

        searches = [
            qdrant.search("raw_memories", vector, limit=3, query_filter=client_filter),
            qdrant.search("cases", vector, limit=3),
            qdrant.search("patterns", vector, limit=2),
            qdrant.search("knowledge", vector, limit=2),
        ]
        results = await asyncio.gather(*searches, return_exceptions=True)
    except Exception:
        results = [[], [], [], []]

    rag = []
    for r in results:
        if isinstance(r, list):
            rag.extend(r)
    rag.sort(key=lambda x: x.score if hasattr(x, "score") else 0, reverse=True)

    logger.debug("Retrieve #%d: %d results", count, len(rag))
    return {
        "query_vector": vector,
        "rag_results": rag[:10],
        "retrieve_count": count,
    }


async def _analyst_node(state: DeepState) -> dict:
    """Analyzes RAG results. If quality is low, requests another retrieve."""
    results = state.get("rag_results", [])

    if not results or state.get("retrieve_count", 0) < 2:
        quality = sum(getattr(r, "score", 0) for r in results[:3]) / max(len(results[:3]), 1)
        if quality < 0.4 and state.get("retrieve_count", 0) < MAX_RETRIEVE_LOOPS:
            refined = await _refine_query(state["message"], results)
            if refined:
                return {"analysis_needs_more_context": True, "refined_query": refined}

    analysis = await _generate_analysis(state["message"], results)
    return {"analysis": analysis, "analysis_needs_more_context": False}


async def _enrich_worker_node(state: DeepState) -> dict:
    """Generate and send enriched response."""
    analysis = state.get("analysis", "")
    results = state.get("rag_results", [])
    fast = state.get("fast_response", "")

    context_parts = [analysis[:500]]
    for r in results[:3]:
        payload = getattr(r, "payload", {})
        snippet = str(payload.get("content", payload.get("snippet", "")))[:200]
        if snippet:
            context_parts.append(snippet)

    system = (
        "Eres un coach profesional. El usuario ya recibió una respuesta rápida. "
        "Ahora profundiza con el siguiente contexto adicional. "
        "Sé breve (2-3 frases). No repitas lo que ya se dijo.\n\n"
        f"Respuesta rápida previa: {fast[:200]}\n"
        f"Contexto adicional:\n" + "\n---\n".join(context_parts[1:])
    )
    response = await _call_llm(system, state["message"])
    logger.info("Enriched response: %d chars", len(response))
    return {"enriched_response": response}


async def _learn_node(state: DeepState) -> dict:
    """Save case and patterns to Qdrant. Reuses query_vector."""
    try:
        from kairos.memory.memory import _embed, _get_qdrant
        from uuid import uuid4

        qdrant = _get_qdrant()
        vector = state.get("query_vector")
        if not vector:
            vector = await _embed(state["message"])

        case_text = f"M:{state['message'][:300]}|R:{state.get('enriched_response','')[:300]}"
        case_vec = vector if case_text == state["message"] else await _embed(case_text)

        from qdrant_client.http.models import PointStruct
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()

        await asyncio.gather(
            qdrant.upsert("cases", points=[
                PointStruct(id=str(uuid4()), vector=case_vec, payload={
                    "content": case_text, "client_id": state.get("client_id", ""),
                    "session_id": state.get("session_id", ""), "timestamp": now,
                })
            ]),
            qdrant.upsert("executions", points=[
                PointStruct(id=str(uuid4()), vector=vector, payload={
                    "message": state["message"][:500],
                    "analysis": state.get("analysis", "")[:200],
                    "timestamp": now,
                })
            ]),
            return_exceptions=True,
        )
    except Exception as e:
        logger.warning("Learn failed: %s", e)
    return {}


async def _alert_check_node(state: DeepState) -> dict:
    """Check risk thresholds and log if needed."""
    risk = state.get("risk_level", "low")
    if risk in ("high", "medium"):
        logger.warning("Alert: risk=%s for client=%s", risk, state.get("client_id", "?"))
    return {}


# ── Helpers ──

async def _refine_query(message: str, results: list) -> str | None:
    try:
        snippets = " | ".join(str(getattr(r, "payload", {}).get("content", ""))[:100] for r in results[:3])
        return f"{message} {snippets}"[:300]
    except Exception:
        return None


async def _generate_analysis(message: str, results: list) -> str:
    snippets = "\n".join(str(getattr(r, "payload", {}).get("content", ""))[:150] for r in results[:5])
    if not snippets.strip():
        return "Sin contexto relevante disponible."
    return f"Contexto:\n{snippets}"


async def _call_llm(system: str, user: str) -> str:
    import os
    import openai
    client = openai.AsyncOpenAI(
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    resp = await client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "deepseek-chat"),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=1024,
    )
    return resp.choices[0].message.content or ""


# ── Public entry point ──

async def run(
    message: str,
    session_id: str,
    client_id: str | None = None,
    coach_id: str = "",
    journey_id: str | None = None,
    channel: str = "web",
    metadata: dict | None = None,
    fast_response: str = "",
    risk_level: str = "low",
) -> None:
    """Run deep path in the background. Does NOT block the fast response."""
    graph = get_deep_graph()
    state: DeepState = {
        "message": message,
        "client_id": client_id or "",
        "coach_id": coach_id,
        "journey_id": journey_id or "",
        "session_id": session_id,
        "channel": channel,
        "metadata": metadata or {},
        "fast_response": fast_response,
        "retrieve_count": 0,
        "risk_level": risk_level,
    }
    try:
        await graph.ainvoke(state)
    except Exception as e:
        logger.error("Deep path failed: %s", e)
