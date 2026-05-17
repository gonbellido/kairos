import json
import logging
from datetime import datetime, timezone
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from kairos.core.state import AgentState, Decision, Evaluation
from kairos.config import get_settings

logger = logging.getLogger(__name__)


async def response_validator(
    state: AgentState,
    llm: ChatOpenAI | None = None,
    plugin_loader=None,
    prompt_store=None,
) -> dict[str, Any]:
    settings = get_settings()
    if llm is None:
        llm = ChatOpenAI(
            model=settings.evaluator_model,
            temperature=0.0,
            api_key=settings.llm_api_key,
        )

    eval_prompt = (
        "You are a response evaluator. Score the following response on a scale 0-1 for:\n"
        "1. Overall quality\n"
        "2. Adherence to the profile's behavioral style (impronta)\n"
        "3. Factual consistency (if applicable)\n"
        "4. Safety (any harmful content?)\n"
        "5. Anti-patterns detected\n\n"
        f"Profile: {state.get('profile_id')}\n"
        f"Impronta rules: {state.get('impronta_rules', [])}\n"
        f"User message: {state['message'][:500]}\n"
        f"Response: {state.get('llm_response', '')[:1000]}\n\n"
        "Respond in JSON: {\"score\": float, \"impronta_adherence\": float, "
        "\"factual_consistency\": float|null, \"safety_check\": bool, "
        "\"feedback\": \"str\", \"anti_patterns_detected\": [\"str\"]}"
    )

    if prompt_store:
        try:
            stored = await prompt_store.get("validator")
            if stored.strip():
                eval_prompt = stored.format(
                    profile=state.get("profile_id", ""),
                    rules=state.get("impronta_rules", []),
                    message=state["message"][:500],
                    response=state.get("llm_response", "")[:1000],
                )
        except Exception:
            pass

    eval_response = await llm.ainvoke([SystemMessage(content=eval_prompt)])

    eval_result: Evaluation = {
        "score": 0.7,
        "impronta_adherence": 0.8,
        "factual_consistency": None,
        "safety_check": True,
        "feedback": "",
        "anti_patterns_detected": [],
    }
    try:
        parsed = json.loads(
            eval_response.content.strip()
            .removeprefix("```json").removesuffix("```").strip()
        )
        for key in eval_result:
            if key in parsed:
                eval_result[key] = parsed[key]
    except (json.JSONDecodeError, AttributeError):
        pass

    # D4: after_validate hook
    profile_id = state.get("profile_id", "")
    if plugin_loader and profile_id:
        eval_result = await plugin_loader.run_hook(
            profile_id, "after_validate", eval_result,
            {"session_id": state.get("session_id", ""), "profile_id": profile_id},
        )

    return {
        "evaluation": eval_result,
        "next_agent": "experience_updater",
    }
