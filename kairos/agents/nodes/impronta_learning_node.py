import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

_utcnow = lambda: datetime.now(tz=timezone.utc)
from kairos.core.state import AgentState, Decision
from kairos.memory.stores.case_store import CaseStore
from kairos.engine.impronta_learner import ImprontaLearner

logger = logging.getLogger(__name__)


async def impronta_learning_node(
    state: AgentState,
    learner: ImprontaLearner,
) -> dict[str, Any]:
    profile_id = state.get("profile_id", "")
    if not profile_id:
        return {"next_agent": "obsidian"}

    adjustments = await learner.adjust(profile_id, window=15, min_samples=3)
    if not adjustments:
        return {"next_agent": "obsidian"}

    adjusted = await learner.apply_adjustments(profile_id, adjustments)
    if adjusted is None:
        return {"next_agent": "obsidian"}

    decision: Decision = {
        "agent": "impronta_learner",
        "action": "adjust",
        "reasoning": f"Adjusted impronta for {profile_id}: {adjustments}",
        "timestamp": _utcnow().isoformat(),
        "data_snapshot": adjustments,
    }

    return {
        "impronta": adjusted,
        "decisions": [decision],
        "next_agent": "obsidian",
    }
