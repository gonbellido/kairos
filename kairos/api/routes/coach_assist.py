from fastapi import APIRouter, Request
from pydantic import BaseModel
from kairos.engine.i18n import get_i18n

router = APIRouter(prefix="/coach", tags=["coach"])

class AskRequest(BaseModel):
    question: str

@router.post("/ask")
async def coach_ask(req: Request, body: AskRequest):
    runtime = req.app.state.runtime

    # Get current coach from session
    token = req.cookies.get("kairos_token")
    coach = None
    if token:
        coach = await req.app.state.coach_db.get_session(token)

    # Use localized coach assistant prompt
    lang = getattr(req.state, "lang", "es")
    prompt = await req.app.state.prompt_store.get("coach_assistant", lang=lang)

    # Standard coach assistant logic (RAG)
    # This is a simplified version of what would be in the actual system
    client_store = runtime.client_store
    raw_store = runtime.raw_store

    coach_id = coach["id"] if coach else "default"

    # Context gathering
    clients = await client_store.search_by_coach(coach_id)
    clients_context = "\n".join([f"- {c.nombre}: {c.estado_actual.emocional}, score {c.progreso.score_global}" for c in clients])

    materials = raw_store.list_by_filter(coach_id=coach_id, limit=10)
    materials_context = "\n".join([f"- {m.get('title', 'Doc')}: {m.get('content', '')[:100]}" for m in materials])

    full_prompt = prompt.format(
        clientes_context=clients_context or "No hay clientes registrados.",
        materiales_context=materials_context or "No hay materiales subidos."
    )

    # Call LLM
    response = await runtime.llm.complete(full_prompt, body.question)

    return {"answer": response}
