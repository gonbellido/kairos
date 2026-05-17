"""Etapa 8.3: Journey CRUD API — coach panel UI endpoints.

Manages journeys, phases, agents, and coach profile from the admin panel.
No YAML files needed. Everything lives in PostgreSQL.
"""

import json
import logging
from uuid import uuid4
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["journeys"])


# ── Schemas ──

class JourneyCreate(BaseModel):
    name: str
    description: str = ""

class JourneyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None

class PhaseCreate(BaseModel):
    name: str
    agent_role: str = ""
    objective: str = ""
    system_prompt: str = ""
    expects_json: bool = False
    tag_mappings: dict | None = None
    allowed_tags: list[str] | None = None
    collects_fields: list[str] | None = None

class PhaseUpdate(BaseModel):
    name: str | None = None
    agent_role: str | None = None
    system_prompt: str | None = None
    expects_json: bool | None = None
    tag_mappings: dict | None = None
    allowed_tags: list[str] | None = None
    collects_fields: list[str] | None = None

class ReorderRequest(BaseModel):
    order: list[str]  # list of phase IDs in desired order

class CoachProfileUpdate(BaseModel):
    directividad: float | None = None
    emocionalidad: float | None = None
    ritmo: float | None = None
    coach_persona: str | None = None
    default_journey_id: str | None = None

class PreviewRequest(BaseModel):
    sample_client_data: dict | None = None
    coach_overrides: dict | None = None


# ── Helpers ──

def _get_sf(req: Request):
    from kairos.db.session import get_session_factory
    return get_session_factory()


def _row_to_dict(row) -> dict:
    return {c.name: str(getattr(row, c.name)) if getattr(row, c.name) is not None else None
            for c in row.__table__.columns}


# ── Journey CRUD ──

@router.get("/coach/{coach_id}/journeys")
async def list_journeys(coach_id: str, req: Request):
    from kairos.db.models import JourneyModel
    from sqlalchemy import select
    sf = _get_sf(req)
    async with sf() as s:
        result = await s.execute(
            select(JourneyModel).where(JourneyModel.coach_id == coach_id)
        )
        journeys = result.scalars().all()
        return [_row_to_dict(j) for j in journeys]


@router.post("/coach/{coach_id}/journeys")
async def create_journey(coach_id: str, body: JourneyCreate, req: Request):
    from kairos.db.models import JourneyModel
    sf = _get_sf(req)
    async with sf() as s:
        j = JourneyModel(
            id=uuid4().hex[:12], coach_id=coach_id,
            name=body.name, description=body.description, status="draft",
        )
        s.add(j)
        await s.commit()
        return _row_to_dict(j)


@router.patch("/journeys/{journey_id}")
async def update_journey(journey_id: str, body: JourneyUpdate, req: Request):
    from kairos.db.models import JourneyModel
    from sqlalchemy import select
    sf = _get_sf(req)
    async with sf() as s:
        result = await s.execute(select(JourneyModel).where(JourneyModel.id == journey_id))
        j = result.scalars().first()
        if not j:
            raise HTTPException(404, "Journey not found")
        if body.name is not None:
            j.name = body.name
        if body.description is not None:
            j.description = body.description
        if body.is_active is not None:
            j.status = "active" if body.is_active else "draft"
        await s.commit()
        return {"ok": True}


@router.delete("/journeys/{journey_id}")
async def delete_journey(journey_id: str, req: Request):
    from kairos.db.models import JourneyModel, ClientJourneyModel
    from sqlalchemy import select
    sf = _get_sf(req)
    async with sf() as s:
        # Check no active clients
        active = await s.execute(
            select(ClientJourneyModel).where(
                ClientJourneyModel.journey_id == journey_id,
                ClientJourneyModel.status.in_(["in_progress", "active"])
            )
        )
        if active.scalars().first():
            raise HTTPException(400, "Cannot delete: journey has active clients")
        await s.execute(
            select(JourneyModel).where(JourneyModel.id == journey_id)
        )
        journey = (await s.execute(select(JourneyModel).where(JourneyModel.id == journey_id))).scalars().first()
        if journey:
            await s.delete(journey)
            await s.commit()
        return {"ok": True}


# ── Phase CRUD ──

@router.get("/journeys/{journey_id}/phases")
async def list_phases(journey_id: str, req: Request):
    from kairos.db.models import JourneyPhaseModel
    from sqlalchemy import select
    sf = _get_sf(req)
    async with sf() as s:
        result = await s.execute(
            select(JourneyPhaseModel)
            .where(JourneyPhaseModel.journey_id == journey_id)
            .order_by(JourneyPhaseModel.order_index)
        )
        return [_row_to_dict(p) for p in result.scalars().all()]


@router.post("/journeys/{journey_id}/phases")
async def create_phase(journey_id: str, body: PhaseCreate, req: Request):
    from kairos.db.models import JourneyPhaseModel, JourneyAgentModel
    from sqlalchemy import select, func
    sf = _get_sf(req)
    async with sf() as s:
        # Get next order_index
        max_order = await s.execute(
            select(func.max(JourneyPhaseModel.order_index))
            .where(JourneyPhaseModel.journey_id == journey_id)
        )
        next_order = (max_order.scalar() or 0) + 1

        phase_id = uuid4().hex[:12]
        phase = JourneyPhaseModel(
            id=phase_id, journey_id=journey_id,
            name=body.name, objective=body.objective,
            order_index=next_order,
        )
        s.add(phase)

        agent = JourneyAgentModel(
            id=uuid4().hex[:12], journey_id=journey_id, phase_id=phase_id,
            name=body.agent_role or body.name, role=body.agent_role,
            system_prompt=body.system_prompt,
            allowed_tags=body.allowed_tags or [],
            output_schema=json.dumps({"expects_json": body.expects_json}) if body.expects_json else None,
            tag_mappings=body.tag_mappings or {},
            collects_fields=body.collects_fields or [],
            order_index=next_order,
        )
        s.add(agent)
        await s.commit()
        return {"id": phase_id, "phase_order": next_order, **body.model_dump()}


@router.put("/journeys/{journey_id}/phases/{phase_id}")
async def update_phase(journey_id: str, phase_id: str, body: PhaseUpdate, req: Request):
    from kairos.db.models import JourneyPhaseModel, JourneyAgentModel
    from sqlalchemy import select
    sf = _get_sf(req)
    async with sf() as s:
        phase_r = await s.execute(select(JourneyPhaseModel).where(JourneyPhaseModel.id == phase_id))
        phase = phase_r.scalars().first()
        if not phase:
            raise HTTPException(404, "Phase not found")
        if body.name is not None:
            phase.name = body.name
        if body.agent_role is not None:
            phase.objective = body.agent_role

        agent_r = await s.execute(select(JourneyAgentModel).where(JourneyAgentModel.phase_id == phase_id))
        agent = agent_r.scalars().first()
        if agent:
            if body.agent_role is not None:
                agent.name = body.agent_role
            if body.system_prompt is not None:
                agent.system_prompt = body.system_prompt
            if body.allowed_tags is not None:
                agent.allowed_tags = body.allowed_tags
            if body.tag_mappings is not None:
                agent.tag_mappings = body.tag_mappings
            if body.collects_fields is not None:
                agent.collects_fields = body.collects_fields

        await s.commit()
        return {"ok": True}


@router.patch("/journeys/{journey_id}/phases/reorder")
async def reorder_phases(journey_id: str, body: ReorderRequest, req: Request):
    from kairos.db.models import JourneyPhaseModel
    from sqlalchemy import select
    sf = _get_sf(req)
    async with sf() as s:
        for i, phase_id in enumerate(body.order, start=1):
            result = await s.execute(select(JourneyPhaseModel).where(JourneyPhaseModel.id == phase_id))
            phase = result.scalars().first()
            if phase:
                phase.order_index = i
        await s.commit()
        return {"ok": True}


@router.delete("/journeys/{journey_id}/phases/{phase_id}")
async def delete_phase(journey_id: str, phase_id: str, req: Request):
    from kairos.db.models import JourneyPhaseModel, JourneyAgentModel
    from sqlalchemy import select
    sf = _get_sf(req)
    async with sf() as s:
        phase_r = await s.execute(select(JourneyPhaseModel).where(JourneyPhaseModel.id == phase_id))
        phase = phase_r.scalars().first()
        if phase:
            await s.delete(phase)
        agent_r = await s.execute(select(JourneyAgentModel).where(JourneyAgentModel.phase_id == phase_id))
        agent = agent_r.scalars().first()
        if agent:
            await s.delete(agent)
        await s.commit()
        return {"ok": True}


# ── Coach profile ──

@router.get("/coach/{coach_id}/profile")
async def get_coach_profile(coach_id: str, req: Request):
    from kairos.db.models import CoachModel
    from sqlalchemy import select
    sf = _get_sf(req)
    async with sf() as s:
        result = await s.execute(select(CoachModel).where(CoachModel.id == coach_id))
        coach = result.scalars().first()
        if not coach:
            raise HTTPException(404, "Coach not found")
        return {
            "directividad": (coach.impronta_data or {}).get("directividad", 0.5),
            "emocionalidad": (coach.impronta_data or {}).get("emocionalidad", 0.5),
            "ritmo": (coach.impronta_data or {}).get("ritmo", 0.5),
            "coach_persona": (coach.impronta_data or {}).get("coach_persona", ""),
            "default_journey_id": coach.default_journey_id or "",
        }


@router.put("/coach/{coach_id}/profile")
async def update_coach_profile(coach_id: str, body: CoachProfileUpdate, req: Request):
    from kairos.db.models import CoachModel
    from sqlalchemy import select
    sf = _get_sf(req)
    async with sf() as s:
        result = await s.execute(select(CoachModel).where(CoachModel.id == coach_id))
        coach = result.scalars().first()
        if not coach:
            raise HTTPException(404, "Coach not found")
        impronta = dict(coach.impronta_data or {})
        if body.directividad is not None:
            impronta["directividad"] = body.directividad
        if body.emocionalidad is not None:
            impronta["emocionalidad"] = body.emocionalidad
        if body.ritmo is not None:
            impronta["ritmo"] = body.ritmo
        if body.coach_persona is not None:
            impronta["coach_persona"] = body.coach_persona
        coach.impronta_data = impronta
        if body.default_journey_id is not None:
            coach.default_journey_id = body.default_journey_id
        await s.commit()
        return {"ok": True}


# ── Preview ──

@router.post("/journeys/{journey_id}/phases/{phase_id}/preview")
async def preview_prompt(journey_id: str, phase_id: str, body: PreviewRequest, req: Request):
    from kairos.db.models import JourneyPhaseModel, JourneyAgentModel
    from sqlalchemy import select
    sf = _get_sf(req)
    async with sf() as s:
        agent_r = await s.execute(select(JourneyAgentModel).where(JourneyAgentModel.phase_id == phase_id))
        agent = agent_r.scalars().first()
        if not agent:
            raise HTTPException(404, "Agent not found")

        try:
            import jinja2
            sample = body.sample_client_data or {}
            overrides = body.coach_overrides or {}
            rendered = jinja2.Template(agent.system_prompt).render(
                directividad=overrides.get("directividad", 0.5),
                emocionalidad=overrides.get("emocionalidad", 0.5),
                ritmo=overrides.get("ritmo", 0.5),
                coach_persona=overrides.get("coach_persona", ""),
                journey_name=journey_id,
                phase_name="Preview",
                phase_order=1,
                total_phases=1,
                progress_pct=0,
                pending_fields=[],
                **sample,
            )
            return {"rendered_prompt": rendered}
        except Exception as e:
            return {"rendered_prompt": agent.system_prompt, "error": str(e)}


# ── Validation ──

@router.get("/journeys/{journey_id}/validate")
async def validate_journey(journey_id: str, req: Request):
    from kairos.db.models import JourneyPhaseModel, JourneyAgentModel
    from sqlalchemy import select
    sf = _get_sf(req)
    async with sf() as s:
        phases_r = await s.execute(select(JourneyPhaseModel).where(JourneyPhaseModel.journey_id == journey_id))
        phases = phases_r.scalars().all()

        errors, warnings = [], []

        if not phases:
            errors.append("El journey no tiene ninguna fase")
            return {"valid": False, "errors": errors, "warnings": warnings}

        valid_orders = {p.order_index for p in phases}

        for phase in phases:
            agent_r = await s.execute(
                select(JourneyAgentModel).where(JourneyAgentModel.phase_id == phase.id)
            )
            agent = agent_r.scalars().first()

            if not agent or not agent.system_prompt.strip():
                errors.append(f"Fase '{phase.name}': prompt vacío")

            if agent and agent.tag_mappings:
                tms = agent.tag_mappings
                if isinstance(tms, str):
                    try:
                        tms = json.loads(tms)
                    except json.JSONDecodeError:
                        tms = {}
                for tag, target in tms.items():
                    try:
                        target_int = int(target) if isinstance(target, str) else target
                    except (ValueError, TypeError):
                        errors.append(f"Fase '{phase.name}': tag '{tag}' tiene valor inválido '{target}'")
                        continue
                    if target_int != 99 and target_int not in valid_orders:
                        errors.append(f"Fase '{phase.name}': tag '{tag}' apunta a fase {target_int} inexistente")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


# ── Available variables ──

@router.get("/journeys/{journey_id}/available-variables")
async def available_variables(journey_id: str, req: Request):
    from kairos.db.models import JourneyPhaseModel, JourneyAgentModel
    from sqlalchemy import select
    sf = _get_sf(req)
    async with sf() as s:
        phases_r = await s.execute(
            select(JourneyPhaseModel)
            .where(JourneyPhaseModel.journey_id == journey_id)
            .order_by(JourneyPhaseModel.order_index)
        )
        phases = phases_r.scalars().all()

        client_vars = {}
        for phase in phases:
            agent_r = await s.execute(
                select(JourneyAgentModel).where(JourneyAgentModel.phase_id == phase.id)
            )
            agent = agent_r.scalars().first()
            if agent and agent.collects_fields:
                fields = agent.collects_fields
                if isinstance(fields, str):
                    try:
                        fields = json.loads(fields)
                    except json.JSONDecodeError:
                        fields = []
                for f in fields:
                    client_vars[f] = f"Recolectado en fase '{phase.name}'"

        from kairos.engine.journey_engine_v2 import COACH_VARIABLES, JOURNEY_VARIABLES
        return {
            "always_available": {**COACH_VARIABLES, **JOURNEY_VARIABLES},
            "client_data": client_vars,
        }
