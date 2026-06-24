"""F6: Journey transition CRUD endpoints for the admin panel."""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from kairos.db.session import create_session_factory
from kairos.engine.journey_engine import JourneyEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["journey_transitions"])


class TransitionCreate(BaseModel):
    from_phase_id: str
    to_phase_id: str = ""
    condition: dict = {}
    priority: int = 0


class TransitionUpdate(BaseModel):
    from_phase_id: str | None = None
    to_phase_id: str | None = None
    condition: dict | None = None
    priority: int | None = None
    is_active: bool | None = None


def _get_engine() -> JourneyEngine:
    return JourneyEngine(create_session_factory())


@router.get("/journeys/{journey_id}/transitions")
async def list_transitions(journey_id: str):
    je = _get_engine()
    return await je.get_transitions(journey_id)


@router.post("/journeys/{journey_id}/transitions")
async def create_transition(journey_id: str, body: TransitionCreate):
    je = _get_engine()
    return await je.add_transition(
        journey_id=journey_id,
        from_phase_id=body.from_phase_id,
        to_phase_id=body.to_phase_id,
        condition=body.condition,
        priority=body.priority,
    )


@router.put("/journeys/transitions/{transition_id}")
async def update_transition(transition_id: str, body: TransitionUpdate):
    je = _get_engine()
    result = await je.update_transition(
        transition_id,
        from_phase_id=body.from_phase_id,
        to_phase_id=body.to_phase_id,
        condition=body.condition,
        priority=body.priority,
        is_active=body.is_active,
    )
    if result is None:
        raise HTTPException(404, "Transition not found")
    return result


@router.delete("/journeys/transitions/{transition_id}")
async def delete_transition(transition_id: str):
    je = _get_engine()
    ok = await je.delete_transition(transition_id)
    if not ok:
        raise HTTPException(404, "Transition not found")
    return {"ok": True}
