import logging
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from kairos.core.memory import CaseMemory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionStartRequest(BaseModel):
    coach_id: str = "default"
    client_id: str = ""
    profile_id: str = "coaching"


class SessionCloseRequest(BaseModel):
    summary: str = ""


@router.post("/start")
async def start_session(req: Request, body: SessionStartRequest):
    sm = req.app.state.runtime.session_manager
    session = sm.start(
        coach_id=body.coach_id,
        client_id=body.client_id,
        profile_id=body.profile_id,
    )
    return {"session_id": session.id, "status": session.status}


@router.post("/{session_id}/close")
async def close_session(req: Request, session_id: str, body: SessionCloseRequest):
    sm = req.app.state.runtime.session_manager
    session = sm.close(session_id, body.summary)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session.id, "status": session.status}


@router.get("/active")
async def list_active(req: Request, coach_id: str = "default"):
    sm = req.app.state.runtime.session_manager
    sessions = sm.list_active(coach_id)
    return {"sessions": [s.model_dump(mode="json") for s in sessions]}


@router.get("/{session_id}")
async def get_session(req: Request, session_id: str):
    sm = req.app.state.runtime.session_manager
    session = sm.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump(mode="json")
