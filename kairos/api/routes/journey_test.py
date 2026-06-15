"""Journey Test API — simulate conversations, diagnose issues, generate reports."""

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from kairos.engine.journey_tester import JourneyTester
from kairos.api.routes.web import _get_coach, _render

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_tester(req: Request) -> JourneyTester:
    tester = getattr(req.app.state, "journey_tester", None)
    if tester is None:
        from kairos.db.session import create_session_factory
        je = getattr(req.app.state, "journey_engine", None)
        if je is None:
            from kairos.engine.journey_engine import JourneyEngine
            sf = create_session_factory()
            je = JourneyEngine(sf)
            req.app.state.journey_engine = je
        else:
            sf = create_session_factory()
        tester = JourneyTester(sf, je)
        req.app.state.journey_tester = tester
    return tester


@router.get("/admin/journeys/{journey_id}/test", response_class=HTMLResponse)
async def journey_test_page(req: Request, journey_id: str):
    coach = await _get_coach(req)
    if not coach or coach.get("role") != "admin":
        return HTMLResponse("No autorizado", status_code=403)

    tester = _get_tester(req)
    je = req.app.state.journey_engine
    journey = await je.get_journey(journey_id)
    if not journey:
        return HTMLResponse("Journey not found", status_code=404)

    from kairos.api.routes.web import _render

    return _render(
        req,
        "admin_journey_test.html",
        {"title": f"Test: {journey['name']}", "coach": coach, "journey": journey},
    )


@router.post("/api/v1/journeys/{journey_id}/test/start")
async def test_start(req: Request, journey_id: str):
    coach = await _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=403)

    tester = _get_tester(req)
    try:
        session = await tester.start_test(journey_id, coach["id"])
        state = await tester.get_state(session.id)
        return {"ok": True, "session_id": session.id, "state": state}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/v1/journeys/{journey_id}/test/message")
async def test_message(req: Request, journey_id: str):
    coach = await _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=403)

    body = await req.json()
    session_id = body.get("session_id", "")
    message = body.get("message", "")

    if not session_id or not message:
        return {"ok": False, "error": "session_id and message required"}

    tester = _get_tester(req)
    try:
        turn = await tester.send_message(session_id, message)
        state = await tester.get_state(session_id)

        return {
            "ok": True,
            "turn": {
                "step": turn.step,
                "agent_name": turn.agent_name,
                "phase_name": turn.phase_name,
                "agent_id": turn.agent_id,
                "phase_id": turn.phase_id,
                "response": turn.llm_response_raw,
                "json_parse_error": turn.json_parse_error,
                "collected_fields": turn.collected_fields,
                "missing_fields": turn.missing_fields,
                "expected_fields": turn.expected_fields,
                "advancement": turn.advancement,
                "duration_ms": turn.duration_ms,
                "error": turn.error,
            },
            "state": state,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/v1/journeys/{journey_id}/test/skip")
async def test_skip(req: Request, journey_id: str):
    coach = await _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=403)

    body = await req.json()
    session_id = body.get("session_id", "")

    tester = _get_tester(req)
    try:
        await tester.skip_agent(session_id)
        state = await tester.get_state(session_id)
        return {"ok": True, "state": state}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/v1/journeys/{journey_id}/test/reset")
async def test_reset(req: Request, journey_id: str):
    coach = await _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=403)

    body = await req.json()
    session_id = body.get("session_id", "")

    tester = _get_tester(req)
    try:
        await tester.reset_test(session_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/v1/journeys/{journey_id}/test/report")
async def test_report(req: Request, journey_id: str):
    coach = await _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=403)

    session_id = req.query_params.get("session_id", "")

    tester = _get_tester(req)
    try:
        report = await tester.generate_report(session_id)
        return {"ok": True, "report": report}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/v1/journeys/{journey_id}/test/prompt/{agent_id}")
async def test_preview_prompt(req: Request, journey_id: str, agent_id: str):
    """Preview the composed prompt for a given agent without calling LLM."""
    coach = await _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=403)

    session_id = req.query_params.get("session_id", "")

    tester = _get_tester(req)
    session = tester.get_session(session_id)
    if not session:
        return {"ok": False, "error": "Session not found"}

    fake_message = req.query_params.get("message", "Hola")
    try:
        prompt = await req.app.state.journey_engine.compose_agent_prompt(
            session.client_id, fake_message
        )
        return {"ok": True, "prompt": prompt}
    except Exception as e:
        return {"ok": False, "error": str(e)}
