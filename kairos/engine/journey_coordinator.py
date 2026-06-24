"""F3: Journey Coordinator — evaluates guard-based transitions by priority.

Transitions complement (not replace) tag_mappings: the existing tag logic runs first;
the coordinator fires afterwards when tag logic did not advance the journey.

Guard types supported in F3:
- ``turns``: ``{"type": "turns", "min": N}``  → turn_count >= N
- ``field``: ``{"type": "field", "field": "x", "op": "present"|"equals", "value": "..."}``
- ``objective_met``: ``{"type": "objective_met", "min_confidence": 0.8}``
"""

import json
import logging

from sqlalchemy import select

from kairos.db.models import JourneyTransitionModel

logger = logging.getLogger(__name__)

_EMPTY = (None, "", [], {})


def _guard_turns(condition: dict, context: dict) -> bool:
    min_turns = condition.get("min", 0)
    return context.get("turn_count", 0) >= min_turns


def _guard_field(condition: dict, context: dict) -> bool:
    field = condition.get("field")
    if not field:
        return False
    collected = context.get("collected", {}) or {}
    value = collected.get(field)
    op = condition.get("op", "present")
    if op == "present":
        return value not in _EMPTY
    if op == "equals":
        return value == condition.get("value")
    return False


def _guard_objective_met(condition: dict, context: dict) -> bool:
    min_confidence = condition.get("min_confidence", 0.8)
    objectives = context.get("objective_state", {}) or {}
    if not objectives:
        return False
    for obj in objectives.values():
        if not isinstance(obj, dict):
            continue
        if obj.get("met") and obj.get("confidence", 0) >= min_confidence:
            return True
    return False


_GUARDS = {
    "turns": _guard_turns,
    "field": _guard_field,
    "objective_met": _guard_objective_met,
}


class JourneyCoordinator:
    def __init__(self, session_factory):
        self._sf = session_factory

    async def resolve_transition(
        self, journey_id: str, current_phase_id: str, context: dict
    ) -> dict | None:
        """Return the first matching transition dict, or None."""
        try:
            async with self._sf() as s:
                result = await s.execute(
                    select(JourneyTransitionModel)
                    .where(JourneyTransitionModel.journey_id == journey_id)
                    .where(JourneyTransitionModel.from_phase_id == current_phase_id)
                    .where(JourneyTransitionModel.is_active == True)
                    .order_by(JourneyTransitionModel.priority.desc())
                )
                transitions = result.scalars().all()
        except Exception as e:
            logger.debug("coordinator: failed to fetch transitions: %s", e)
            return None

        for t in transitions:
            cond = t.condition or {}
            if isinstance(cond, str):
                try:
                    cond = json.loads(cond)
                except (json.JSONDecodeError, ValueError):
                    continue
            guard_type = cond.get("type")
            if not guard_type:
                continue
            evaluator = _GUARDS.get(guard_type)
            if evaluator and evaluator(cond, context):
                return {
                    "transition_id": t.id,
                    "to_phase_id": t.to_phase_id,
                    "condition_type": guard_type,
                }

        return None
