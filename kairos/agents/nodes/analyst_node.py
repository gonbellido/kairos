import json
import logging
from datetime import datetime, timezone
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from kairos.core.state import AgentState, Decision
from kairos.memory.stores.client_store import ClientStore
from kairos.config import get_settings

logger = logging.getLogger(__name__)

ANALYST_PROMPT = """Eres un analista de sesiones de coaching. Revisa el contexto completo y genera:

1. **Resumen del estado actual** del cliente basado en su perfil
2. **Patrones relevantes** de experiencias previas similares
3. **Recomendación de enfoque**: qué tipo de intervención usar
4. **Señales a monitorear**: qué observar durante la interacción

Basado en:
- Clasificación de estado: {state}
- Casos recuperados: {case_count} (score promedio: {avg_score})
- Perfil del cliente: {client_info}
- Patrones detectados: {patterns}

Responde en JSON:
{{
  "summary": "str",
  "recommended_approach": "str",
  "signals_to_monitor": ["str"],
  "risk_flags": ["str"]
}}
"""


async def analyst_node(
    state: AgentState,
    client_store: ClientStore | None = None,
    llm: ChatOpenAI | None = None,
    prompt_store=None,
) -> dict[str, Any]:
    settings = get_settings()
    if llm is None:
        llm = ChatOpenAI(
            model=settings.evaluator_model,
            temperature=0.0,
            api_key=settings.llm_api_key,
        )

    ranked = state.get("ranked_cases", [])
    avg_score = sum(r.composite_score for r in ranked) / max(len(ranked), 1)

    client_id = state.get("context", {}).get("client_id", "")
    client_info = ""
    client_patterns = ""
    if client_id and client_store:
        profile = client_store.get_profile(client_id)
        if profile:
            client_info = (
                f"Emocional: {profile.estado_actual.emocional}, "
                f"Claridad: {profile.estado_actual.claridad}, "
                f"Resistencia: {profile.estado_actual.resistencia}"
            )
            client_patterns = "; ".join(p.patron for p in profile.patrones_detectados[-5:])

    analyst_prompt = ANALYST_PROMPT
    if prompt_store:
        try:
            analyst_prompt = await prompt_store.get("analyst")
        except Exception:
            pass

    prompt = analyst_prompt.format(
        state=state.get("state_classification", {}),
        case_count=len(ranked),
        avg_score=round(avg_score, 2),
        client_info=client_info or "N/A",
        patterns=client_patterns or "N/A",
    )

    result = await llm.ainvoke([SystemMessage(content=prompt)])
    analysis = {}

    try:
        analysis = json.loads(
            result.content.strip()
            .removeprefix("```json").removesuffix("```").strip()
        )
    except (json.JSONDecodeError, AttributeError):
        pass

    decision: Decision = {
        "agent": "analyst",
        "action": "analyze",
        "reasoning": analysis.get("summary", "Analysis complete")[:200],
        "timestamp": _utcnow().isoformat(),
        "data_snapshot": {
            "approach": analysis.get("recommended_approach", ""),
            "risks": len(analysis.get("risk_flags", [])),
        },
    }

    return {
        "decisions": [decision],
        "insights": state.get("insights", []) + [{
            "type": "analyst_recommendation",
            "title": analysis.get("recommended_approach", ""),
            "summary": analysis.get("summary", ""),
        }],
        "context": {
            **state.get("context", {}),
            "_analyst_risk_flags": analysis.get("risk_flags", []),
        },
        "next_agent": "worker",
    }
