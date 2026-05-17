from datetime import datetime, timezone
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
from kairos.core.state import AgentState, Decision
from kairos.engine.state_classifier import StateClassifier


async def perception_node(state: AgentState, classifier: StateClassifier, prompt_store=None) -> dict[str, Any]:
    if prompt_store:
        classifier._prompt_store = prompt_store
    classification = await classifier.classify(
        message=state["message"],
        context=state.get("context"),
    )

    decision: Decision = {
        "agent": "perception",
        "action": "classify",
        "reasoning": f"Classified as: {classification['intencion']} / {classification['emocion']}",
        "timestamp": _utcnow().isoformat(),
        "data_snapshot": {
            "riesgo": classification["riesgo"],
            "urgencia": classification["urgencia"],
        },
    }

    return {
        "state_classification": classification,
        "decisions": [decision],
        "next_agent": "memory",
    }
