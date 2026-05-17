import logging
from datetime import datetime, timezone
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
from kairos.core.state import AgentState, Decision
from kairos.core.scoring_context import ScoringContext
from kairos.core.memory import ScoredCase
from kairos.memory.scoring import ScoringEngine, ScoringWeights

logger = logging.getLogger(__name__)


async def score_node(
    state: AgentState,
    scoring_engine: ScoringEngine,
    profile_engine=None,
    metrics=None,
) -> dict[str, Any]:
    raw_cases = state.get("retrieved_cases", [])
    scored = raw_cases if raw_cases and hasattr(raw_cases[0], 'semantic_score') else [
        ScoredCase(case=c, semantic_score=0.0) for c in raw_cases
    ]

    scoring_ctx = ScoringContext(
        state=state.get("state_classification"),
        profile_id=state.get("profile_id", ""),
        impronta_values=(
            state.get("impronta").model_dump() if state.get("impronta") else {}
        ),
        session_depth=len(state.get("decisions", [])),
    )

    engine = scoring_engine
    if profile_engine:
        try:
            profile = await profile_engine.get_profile(state.get("profile_id", ""))
            if profile and profile.scoring_weights:
                weights = ScoringWeights.from_dict(profile.scoring_weights)
                engine = ScoringEngine(weights)
        except Exception as e:
            logger.warning("Failed to load profile scoring weights, using defaults: %s", e)

    ranked = await engine.score(scored, scoring_ctx)
    selected = engine.select_top(ranked)

    avg_score = sum(r.composite_score for r in selected) / max(len(selected), 1)

    # C2: registrar scores compuestos para distribuciones
    if metrics:
        for r in selected:
            metrics.record_composite_score(r.composite_score)

    decision: Decision = {
        "agent": "score",
        "action": "rank",
        "reasoning": f"Scored {len(raw_cases)} cases, selected {len(selected)} (avg: {avg_score:.2f})",
        "timestamp": _utcnow().isoformat(),
        "data_snapshot": {
            "total_cases": len(raw_cases),
            "selected": len(selected),
            "avg_score": round(avg_score, 3),
        },
    }

    return {
        "ranked_cases": selected,
        "decisions": [decision],
        "next_agent": "aggregate",
    }
