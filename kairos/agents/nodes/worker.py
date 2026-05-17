from datetime import datetime, timezone
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from kairos.core.state import AgentState, Decision
from kairos.core.memory import CaseMemory, CaseMetadata, ExecutionMemory
from kairos.core.impronta import Impronta
from kairos.engine.profile_engine import ProfileEngine
from kairos.engine.prompt_engine import PromptEngine
from kairos.memory.stores import CaseStore, ExecutionStore
from kairos.config import get_settings
from kairos.engine.activity import log_activity


async def worker_node(
    state: AgentState,
    profile_engine: ProfileEngine,
    prompt_engine: PromptEngine,
    case_store: CaseStore,
    execution_store: ExecutionStore,
    llm: ChatOpenAI | None = None,
    plugin_loader=None,
) -> dict[str, Any]:
    settings = get_settings()
    if llm is None:
        llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.llm_api_key,
        )

    profile_id = state["profile_id"]
    profile = await profile_engine.get_profile(profile_id)
    impronta = await profile_engine.resolve_impronta(
        profile_id,
        state.get("context", {}).get("impronta_overrides"),
    )

    # D4: cargar plugins para este perfil
    if plugin_loader and profile.plugins:
        plugin_loader.load_for_profile(profile_id, profile.plugins)

    # D4: before_prompt hook
    prompt_context = {
        "session_id": state.get("session_id", ""),
        "profile_id": profile_id,
        "message": state["message"],
        "state_classification": state.get("state_classification"),
    }
    if plugin_loader:
        await plugin_loader.run_hook(profile_id, "before_prompt", prompt_context)

    prompt = await prompt_engine.build(
        profile=profile,
        impronta=impronta,
        impronta_rules=state.get("impronta_rules"),
        state_classification=state.get("state_classification"),
        cases=state.get("ranked_cases", []),
        patterns=state.get("patterns", []),
        insights=state.get("insights"),
        knowledge_docs=state.get("knowledge_docs", []),
        message=state["message"],
        context=state.get("context"),
    )

    # Fase I: Journey agent prompt — defines agent behavior per phase
    journey_prompt = state.get("journey_system_prompt") or state.get("context", {}).get("_journey_system_prompt", "")
    if journey_prompt:
        prompt = journey_prompt
        # Use raw openai SDK to ensure response_format is passed
        import openai
        client = openai.AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        resp = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": state["message"]},
            ],
            temperature=0.3,
            max_tokens=settings.llm_max_tokens,
            response_format={"type": "json_object"},
        )
        llm_text = resp.choices[0].message.content or ""
        log_activity("prompt_used", {"client_id": state.get("context", {}).get("client_id", ""),
                      "journey": True, "json_mode": True, "prompt_len": len(prompt)})
    else:
        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=state["message"]),
        ])
        llm_text = response.content
        log_activity("prompt_default", {"client_id": state.get("context", {}).get("client_id", ""),
                      "journey": False, "prompt_len": len(prompt)})

    # D4: after_llm hook
    if plugin_loader:
        llm_text = await plugin_loader.run_hook(
            profile_id, "after_llm", llm_text, prompt_context
        )

    decision: Decision = {
        "agent": "worker",
        "action": "generate",
        "reasoning": f"Generated response for profile '{profile_id}'",
        "timestamp": _utcnow().isoformat(),
        "data_snapshot": {
            "prompt_length": len(prompt),
            "response_length": len(llm_text),
        },
    }

    return {
        "profile": profile,
        "impronta": impronta,
        "prompt": prompt,
        "llm_response": llm_text,
        "decisions": [decision],
        "next_agent": "validate",
    }
