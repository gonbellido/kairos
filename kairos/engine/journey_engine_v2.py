"""Etapa 8.2: Journey engine v2 — 100% PostgreSQL-driven, Jinja2 templates, dynamic phases.

Usage:
    from kairos.engine.journey_engine_v2 import JourneyEngineV2
    engine = JourneyEngineV2(session_factory)
    prompt = await engine.compose_agent_prompt(client_id, coach_id, journey_id)
    result = await engine.validate_and_advance(client_id, coach_id, journey_id, agent_response)
"""

import json
import logging
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy import select
from kairos.db.models import (
    JourneyModel, JourneyPhaseModel, JourneyAgentModel,
    ClientJourneyModel, ClientSharedProfileModel, JourneyEventModel,
    CoachModel,
)

logger = logging.getLogger(__name__)
_utcnow = lambda: datetime.now(tz=timezone.utc)


# ── Variables always available in prompts ──

COACH_VARIABLES = {
    "directividad": "Nivel de directividad (0.0-1.0)",
    "emocionalidad": "Nivel de empatía (0.0-1.0)",
    "ritmo": "Velocidad del proceso (0.0-1.0)",
    "coach_persona": "Descripción de personalidad del coach",
}

JOURNEY_VARIABLES = {
    "journey_name": "Nombre del journey",
    "phase_name": "Nombre de esta fase",
    "phase_order": "Número de fase actual",
    "total_phases": "Total de fases",
    "progress_pct": "Porcentaje de avance (0-100)",
    "pending_fields": "Campos aún no recolectados",
}


class JourneyEngineV2:
    def __init__(self, session_factory):
        self._sf = session_factory

    # ── Client journey state ──

    async def get_client_journey(self, client_id: str) -> dict | None:
        async with self._sf() as s:
            result = await s.execute(
                select(ClientJourneyModel)
                .where(ClientJourneyModel.client_id == client_id)
                .order_by(ClientJourneyModel.created_at.desc())
            )
            cj = result.scalars().first()
            if not cj:
                return None
            d = {c.name: getattr(cj, c.name) for c in cj.__table__.columns}
            d["journey"] = await self._get_journey(s, cj.journey_id)
            sp = await self._get_shared_profile(s, client_id)
            d["shared_profile"] = sp
            return d

    async def _get_journey(self, s, journey_id: str) -> dict | None:
        result = await s.execute(
            select(JourneyModel).where(JourneyModel.id == journey_id)
        )
        j = result.scalars().first()
        if not j:
            return None
        journey = {c.name: getattr(j, c.name) for c in j.__table__.columns}
        journey["phases"] = await self._get_phases(s, journey_id)
        journey["agents"] = await self._get_agents(s, journey_id)
        return journey

    async def _get_phases(self, s, journey_id: str) -> list[dict]:
        result = await s.execute(
            select(JourneyPhaseModel)
            .where(JourneyPhaseModel.journey_id == journey_id)
            .order_by(JourneyPhaseModel.order_index)
        )
        return [{c.name: getattr(p, c.name) for c in p.__table__.columns} for p in result.scalars().all()]

    async def _get_agents(self, s, journey_id: str) -> list[dict]:
        result = await s.execute(
            select(JourneyAgentModel)
            .where(JourneyAgentModel.journey_id == journey_id)
            .order_by(JourneyAgentModel.order_index)
        )
        return [{c.name: getattr(a, c.name) for c in a.__table__.columns} for a in result.scalars().all()]

    async def _get_shared_profile(self, s, client_id: str) -> dict | None:
        result = await s.execute(
            select(ClientSharedProfileModel)
            .where(ClientSharedProfileModel.client_id == client_id)
        )
        sp = result.scalars().first()
        if not sp:
            return None
        return {c.name: getattr(sp, c.name) for c in sp.__table__.columns}

    # ── Prompt composition (100% dynamic) ──

    async def compose_agent_prompt(
        self, client_id: str, coach_id: str, journey_id: str, message: str = ""
    ) -> str:
        """Build agent prompt from PostgreSQL. Uses Jinja2 template rendering."""
        cj_data = await self.get_client_journey(client_id)
        if not cj_data or not cj_data.get("journey"):
            return ""

        journey = cj_data["journey"]
        phases = journey.get("phases", [])
        agents = journey.get("agents", [])
        current_phase_id = cj_data.get("current_phase_id")
        current_agent_id = cj_data.get("current_agent_id")

        agent_data = next((a for a in agents if a["id"] == current_agent_id), agents[0] if agents else {})
        phase_data = next((p for p in phases if p["id"] == current_phase_id), phases[0] if phases else {})

        system_prompt = agent_data.get("system_prompt", "")
        if not system_prompt.strip():
            return ""

        # Coach profile (from coaches table)
        coach_data = await self._get_coach_data(coach_id)
        collected = self._get_collected_data(cj_data)
        total_phases = len(phases)
        current_order = phase_data.get("order_index", 0)
        collects_fields = agent_data.get("collects_fields", [])

        template_vars = {
            **coach_data,
            "journey_name": journey.get("name", ""),
            "phase_name": phase_data.get("name", "?"),
            "phase_order": current_order + 1,
            "total_phases": total_phases,
            "progress_pct": int(((current_order + 1) / max(total_phases, 1)) * 100),
            **collected,
            "pending_fields": [f for f in collects_fields if f not in collected],
        }

        try:
            import jinja2
            prompt = jinja2.Template(system_prompt).render(**template_vars)
        except Exception:
            prompt = system_prompt

        # Add collected data section if not already in template
        if collected and "{{" not in system_prompt:
            prompt += "\n\n## Datos recolectados\n"
            prompt += "\n".join(f"- {k}: {v}" for k, v in collected.items())

        # Add state
        prompt += f"""

## Estado
- Journey: {journey.get('name', '')}
- Fase: {phase_data.get('name', '?')}
- Progreso: {template_vars['progress_pct']}%

## Mensaje del cliente
{message}
"""
        return prompt

    async def _get_coach_data(self, coach_id: str) -> dict:
        try:
            async with self._sf() as s:
                result = await s.execute(
                    select(CoachModel).where(CoachModel.id == coach_id)
                )
                coach = result.scalars().first()
                if coach and coach.impronta_data:
                    return dict(coach.impronta_data)
        except Exception:
            pass
        return {"directividad": 0.5, "emocionalidad": 0.5, "ritmo": 0.5, "coach_persona": ""}

    def _get_collected_data(self, cj_data: dict) -> dict:
        collected = cj_data.get("collected_data", {}) or {}
        if isinstance(collected, str):
            try:
                collected = json.loads(collected)
            except json.JSONDecodeError:
                collected = {}
        return collected

    # ── Validation and advancement ──

    async def validate_and_advance(
        self, client_id: str, coach_id: str, journey_id: str, agent_response: dict
    ) -> dict:
        """Save collected data, resolve next phase, advance if tags trigger transition."""
        result = {"advanced": False, "next_phase_order": None, "completed": False, "message": ""}

        async with self._sf() as s:
            cj_result = await s.execute(
                select(ClientJourneyModel)
                .where(ClientJourneyModel.client_id == client_id)
                .where(ClientJourneyModel.journey_id == journey_id)
            )
            cj = cj_result.scalars().first()
            if not cj:
                return result

            # Merge collected data
            current_collected = cj.collected_data or {}
            if isinstance(current_collected, str):
                try:
                    current_collected = json.loads(current_collected)
                except json.JSONDecodeError:
                    current_collected = {}

            new_data = agent_response.get("structured", {})
            if isinstance(new_data, dict):
                collected = new_data.get("collected_data", new_data)
                if isinstance(collected, dict):
                    current_collected = {**current_collected, **{k: v for k, v in collected.items() if v and not k.startswith("_")}}

            cj.collected_data = current_collected
            cj.updated_at = _utcnow()

            # Get current agent for tag resolution
            agent_result = await s.execute(
                select(JourneyAgentModel).where(JourneyAgentModel.id == cj.current_agent_id)
            )
            agent = agent_result.scalars().first()

            # Get phases for this journey
            phases_result = await s.execute(
                select(JourneyPhaseModel)
                .where(JourneyPhaseModel.journey_id == journey_id)
                .order_by(JourneyPhaseModel.order_index)
            )
            phases = phases_result.scalars().all()
            total_phases = len(phases)
            current_phase = next((p for p in phases if p.id == cj.current_phase_id), None)
            current_order = current_phase.order_index if current_phase else 0

            # Resolve next phase
            suggested_tags = agent_response.get("suggested_tags", [])
            tag_mappings = agent.tag_mappings if agent and agent.tag_mappings else {}
            if isinstance(tag_mappings, str):
                try:
                    tag_mappings = json.loads(tag_mappings)
                except json.JSONDecodeError:
                    tag_mappings = {}

            next_order = self._resolve_next_phase(current_order, suggested_tags, tag_mappings, total_phases)

            if next_order is None:
                cj.status = "completed"
                cj.completed_at = _utcnow()
                result["completed"] = True
            else:
                next_phase = next((p for p in phases if p.order_index == next_order), None)
                if next_phase:
                    cj.current_phase_id = next_phase.id
                    cj.current_phase_order = next_order
                    cj.progress_pct = int((next_order / max(total_phases, 1)) * 100)
                    result["advanced"] = True
                    result["next_phase_order"] = next_order

            await s.commit()

            # Log event
            await self._log_event(s, client_id, coach_id, journey_id,
                "phase_advanced" if result["advanced"] else "data_collected",
                {"from_order": current_order, "to_order": next_order, "tags": suggested_tags})

        return result

    def _resolve_next_phase(
        self, current_order: int, suggested_tags: list, tag_mappings: dict, total_phases: int
    ) -> int | None:
        for tag in suggested_tags:
            if tag in tag_mappings:
                target = tag_mappings[tag]
                if isinstance(target, str):
                    target = int(target)
                if target == 99:
                    return None
                if 0 <= target <= total_phases:
                    return target
        next_order = current_order + 1
        return None if next_order > total_phases else next_order

    async def _log_event(self, s, client_id, coach_id, journey_id, event_type, payload):
        try:
            ev = JourneyEventModel(
                id=uuid4().hex[:12], client_id=client_id, coach_id=coach_id,
                journey_id=journey_id, event_type=event_type,
                payload_data=payload or {},
            )
            s.add(ev)
            await s.commit()
        except Exception as e:
            logger.warning("Failed to log journey event: %s", e)
