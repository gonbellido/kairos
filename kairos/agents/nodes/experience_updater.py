from datetime import datetime, timezone
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
from kairos.core.state import AgentState, Decision, Evaluation
from kairos.core.memory import CaseMemory, CaseMetadata, PatternMemory, ExecutionMemory
from kairos.memory.stores import CaseStore, PatternStore, ExecutionStore
from kairos.engine.confidence_calculator import ConfidenceCalculator


async def experience_updater(
    state: AgentState,
    case_store: CaseStore,
    pattern_store: PatternStore,
    execution_store: ExecutionStore,
    pp: int = 0,
    **kwargs: Any,
) -> dict[str, Any]:
    eval_result = state.get("evaluation", {})

    case = CaseMemory(
        profile_id=state["profile_id"],
        client_id=state.get("context", {}).get("client_id", ""),
        context=state["message"],
        intervention=state.get("llm_response", ""),
        impronta_applied=state.get("impronta"),
        outcome=eval_result.get("score"),
        state_classification=dict(state.get("state_classification", {})),
        knowledge_used=[d.get("id", "") for d in state.get("knowledge_docs", [])],
        metadata=CaseMetadata(
            category=state.get("context", {}).get("category", "general"),
            outcome=eval_result.get("score"),
        ),
    )
    case_id = await case_store.store(case)

    for rc in state.get("ranked_cases", []):
        case_store.increment_usage(rc.case.id)

    confidence, conf_details = ConfidenceCalculator.calculate(
        ranked_cases=state.get("ranked_cases", []),
        evaluation_score=eval_result.get("score", 0.7),
        impronta_adherence=eval_result.get("impronta_adherence", 0.8),
        case_count=len(state.get("retrieved_cases", [])),
    )

    exec_mem = ExecutionMemory(
        session_id=state["session_id"],
        profile_id=state["profile_id"],
        client_id=state.get("context", {}).get("client_id", ""),
        input_text=state["message"],
        output_text=state.get("llm_response", ""),
        impronta_used=state.get("impronta"),
        state_classification=dict(state.get("state_classification", {})),
        cases_used=[rc.case.id for rc in state.get("ranked_cases", [])],
    )
    await execution_store.store(exec_mem)

    decision: Decision = {
        "agent": "experience_updater",
        "action": "store",
        "reasoning": f"Stored case {case_id}, confidence: {confidence}",
        "timestamp": _utcnow().isoformat(),
        "data_snapshot": {
            "case_id": case_id,
            "confidence": confidence,
            "eval_score": eval_result.get("score"),
        },
    }

    return {
        "final_response": state.get("llm_response", ""),
        "confidence": confidence,
        "confidence_details": conf_details,
        "execution": exec_mem,
        "decisions": [decision],
        "next_agent": "__end__",
    }
