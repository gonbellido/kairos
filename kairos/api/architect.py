from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from kairos.engine.journey_architect.architect import JourneyArchitect
from kairos.engine.journey_architect.methodology_store import CoachMethodologyStore
from kairos.config.llm_factory import create_llm

router = APIRouter(tags=["architect"])


def _get_coach(req: Request):
    return getattr(req.state, "coach", None)


def _get_architect(req: Request) -> JourneyArchitect:
    if not hasattr(req.app.state, "journey_architect"):
        llm = create_llm()
        ms = CoachMethodologyStore(req.app.state._session_factory)
        req.app.state.journey_architect = JourneyArchitect(
            llm=llm,
            journey_engine=req.app.state.journey_engine,
            methodology_store=ms,
        )
        req.app.state.methodology_store = ms
    return req.app.state.journey_architect


@router.post("/api/v1/architect/build")
async def architect_build(req: Request):
    coach = _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False, "detail": "unauthorized"}, status_code=403)
    body = await req.json()
    prompt = body.get("prompt", "")
    existing_journey_id = body.get("existing_journey_id")
    if not prompt:
        return JSONResponse({"ok": False, "detail": "prompt required"}, status_code=400)
    arch = _get_architect(req)
    result = await arch.build_from_prompt(
        coach_id=coach["id"],
        prompt=prompt,
        existing_journey_id=existing_journey_id,
    )
    return {"ok": True, **result}


@router.post("/api/v1/architect/create")
async def architect_create(req: Request):
    coach = _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False, "detail": "unauthorized"}, status_code=403)
    body = await req.json()
    spec = body.get("journey_spec") or body.get("journey")
    if not spec:
        return JSONResponse({"ok": False, "detail": "journey_spec required"}, status_code=400)
    arch = _get_architect(req)
    try:
        journey_id = await arch.create_journey_from_spec(coach_id=coach["id"], spec=spec)
        return {"ok": True, "journey_id": journey_id}
    except ValueError as e:
        return JSONResponse({"ok": False, "detail": str(e)}, status_code=422)


@router.post("/api/v1/architect/explain/{journey_id}")
async def architect_explain(req: Request, journey_id: str):
    coach = _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False, "detail": "unauthorized"}, status_code=403)
    arch = _get_architect(req)
    explanation = await arch.explain_journey(journey_id)
    return {"ok": True, "explanation": explanation}


@router.post("/api/v1/architect/suggest/{journey_id}")
async def architect_suggest(req: Request, journey_id: str):
    coach = _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False, "detail": "unauthorized"}, status_code=403)
    arch = _get_architect(req)
    suggestions = await arch.suggest_improvements(journey_id=journey_id, coach_id=coach["id"])
    return {"ok": True, "suggestions": suggestions}


@router.get("/api/v1/architect/methodology")
async def get_methodology(req: Request):
    coach = _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False, "detail": "unauthorized"}, status_code=403)
    _get_architect(req)
    ms: CoachMethodologyStore = req.app.state.methodology_store
    docs = await ms.list_methodology_docs(coach["id"])
    return {"ok": True, "docs": docs}


@router.post("/api/v1/architect/methodology")
async def add_methodology(req: Request):
    coach = _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False, "detail": "unauthorized"}, status_code=403)
    body = await req.json()
    _get_architect(req)
    ms: CoachMethodologyStore = req.app.state.methodology_store
    doc_id = await ms.save_methodology(
        coach_id=coach["id"],
        content=body.get("content", ""),
        title=body.get("title", ""),
        source=body.get("source", "text"),
    )
    return {"ok": True, "doc_id": doc_id}


@router.delete("/api/v1/architect/methodology/{doc_id}")
async def delete_methodology(req: Request, doc_id: str):
    coach = _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False, "detail": "unauthorized"}, status_code=403)
    _get_architect(req)
    ms: CoachMethodologyStore = req.app.state.methodology_store
    ok = await ms.delete_doc(coach_id=coach["id"], doc_id=doc_id)
    return {"ok": ok}
