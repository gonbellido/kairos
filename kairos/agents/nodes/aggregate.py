from datetime import datetime, timezone
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
from kairos.core.state import AgentState, Decision
from kairos.engine.pattern_generator import PatternGenerator
from kairos.engine.imprint_mapper import ImprintMapper


async def aggregate_node(
    state: AgentState,
    pattern_generator: PatternGenerator,
    imprint_mapper: ImprintMapper,
) -> dict[str, Any]:
    impronta = state.get("impronta")
    impronta_rules = []
    if impronta:
        impronta_rules = imprint_mapper.map(impronta)

    retrieved = state.get("retrieved_cases", [])
    insights = await pattern_generator.generate_insights(retrieved)

    context_signature = f"{state.get('profile_id')}:{state.get('message', '')[:50]}"

    decision: Decision = {
        "agent": "aggregate",
        "action": "aggregate",
        "reasoning": f"Generated {len(insights)} insights, {len(impronta_rules)} rules",
        "timestamp": _utcnow().isoformat(),
        "data_snapshot": {
            "insight_count": len(insights),
            "impronta_rules": len(impronta_rules),
        },
    }

    return {
        "impronta_rules": impronta_rules,
        "insights": insights,
        "context_signature": context_signature,
        "decisions": [decision],
        "next_agent": "worker",
    }
