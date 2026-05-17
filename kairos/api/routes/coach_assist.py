import logging
from fastapi import APIRouter, Request
from pydantic import BaseModel
from kairos.engine.coach_assistant import CoachAssistant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/coach", tags=["coach"])

_assistant = None


def _get_assistant(prompt_store=None):
    global _assistant
    if _assistant is None:
        _assistant = CoachAssistant(prompt_store=prompt_store)
    elif prompt_store and not _assistant._prompt_store:
        _assistant._prompt_store = prompt_store
    return _assistant


class AskRequest(BaseModel):
    question: str


@router.post("/ask")
async def coach_ask(req: Request, body: AskRequest):
    token = req.cookies.get("kairos_token")
    coach = await req.app.state.coach_db.get_session(token) if token else None
    if not coach:
        return {"answer": "No autorizado. Inicia sesión primero."}

    runtime = req.app.state.runtime
    store = runtime.client_store
    raw_store = runtime.raw_store

    # 1. Clientes del coach
    clients = await store.search_by_coach(coach["id"])

    # 2. Búsqueda semántica sobre TODOS los chunks de materiales
    materials_ctx = "No hay materiales relevantes para esta consulta."
    try:
        relevant = await raw_store.search_relevant(
            query_text=body.question,
            profile_id="coaching",
            client_id="",
            coach_id=coach["id"],
            top_k=8,
        )
        if relevant:
            # Agrupar chunks por documento para contexto coherente
            docs: dict[str, list[dict]] = {}
            for m in relevant:
                doc_id = m.get("metadata", {}).get("document_id", m.get("_point_id", ""))
                if doc_id not in docs:
                    docs[doc_id] = []
                docs[doc_id].append(m)

            parts = ["## Materiales relevantes a tu consulta"]
            for doc_id, chunks in docs.items():
                chunks.sort(key=lambda c: c.get("metadata", {}).get("chunk_index", 0))
                name = chunks[0].get("metadata", {}).get("original_name", "documento")
                score = max(c.get("_score", 0) for c in chunks)
                chunk_total = chunks[0].get("metadata", {}).get("chunk_total", 1)

                content_parts = []
                for c in chunks:
                    idx = c.get("metadata", {}).get("chunk_index", 0)
                    content_parts.append(c.get("content", ""))

                full_content = "\n[...]\n".join(content_parts)
                parts.append(
                    f"\n### {name} (score: {score:.3f}, {len(chunks)}/{chunk_total} chunks relevantes)\n"
                    f"{full_content}"
                )
            materials_ctx = "\n".join(parts)
    except Exception as e:
        logger.warning("Materials semantic search failed: %s", e)

    answer = await _get_assistant(req.app.state.prompt_store).ask(
        body.question, clients, materials_ctx
    )
    return {"answer": answer}
