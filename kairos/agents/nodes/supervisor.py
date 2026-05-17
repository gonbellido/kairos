from datetime import datetime, timezone
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from kairos.core.state import AgentState, Decision, StateClassification
from kairos.config import get_settings

ROUTER_PROMPT = """Eres un router de mensajes para un sistema multi-agente de coaching.
Analiza el mensaje del usuario y determina:

1. **Perfil más adecuado** para responder (coaching, comercial, financiero)
2. **Intención** del mensaje
3. **Confianza** en la clasificación (0-1)
4. **Si requiere acción inmediata** (alerta)

Considera:
- coaching: preguntas existenciales, relaciones, desarrollo personal, liderazgo, equipo
- comercial: ventas, objeciones, pricing, competencia, negociación
- financiero: inversiones, riesgo, ahorro, planificación financiera, números

Responde JSON:
{
  "profile_id": "coaching|comercial|financiero",
  "intention": "str",
  "confidence": 0.0-1.0,
  "requires_immediate_action": bool,
  "reasoning": "str"
}
"""


async def supervisor_node(state: AgentState, llm: ChatOpenAI | None = None, prompt_store=None) -> dict[str, Any]:
    settings = get_settings()
    if llm is None:
        llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=0.0,
            max_tokens=512,
            api_key=settings.llm_api_key,
        )

    profile_id = state.get("profile_id", "coaching")
    message = state["message"]

    # Prompt from store or fallback
    router_prompt = ROUTER_PROMPT
    if prompt_store:
        try:
            router_prompt = await prompt_store.get("supervisor")
        except Exception:
            pass

    # If user explicitly requests a profile via prefix, use it directly
    prefixes = {
        "/coaching": "coaching",
        "/comercial": "comercial",
        "/financiero": "financiero",
    }
    for prefix, target in prefixes.items():
        if message.strip().lower().startswith(prefix):
            clean_msg = message.strip()[len(prefix):].strip()
            decision: Decision = {
                "agent": "supervisor",
                "action": "route_explicit",
                "reasoning": f"Explicit route to {target} via prefix",
                "timestamp": _utcnow().isoformat(),
                "data_snapshot": {"profile": target},
            }
            return {
                "profile_id": target,
                "message": clean_msg,
                "next_agent": "perception",
                "decisions": [decision],
            }

    # LLM-based routing (best-effort)
    import json
    routed_profile = profile_id
    confidence = 0.3
    try:
        result = await llm.ainvoke([
            SystemMessage(content=router_prompt),
            HumanMessage(content=f"Mensaje: {message}\nPerfil actual: {profile_id}"),
        ])
        raw = result.content.strip().removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(raw)
        routed_profile = parsed.get("profile_id", profile_id)
        confidence = parsed.get("confidence", 0.3)
    except Exception:
        pass

    decision: Decision = {
        "agent": "supervisor",
        "action": "route",
        "reasoning": f"Routed to {routed_profile} (confidence: {confidence:.2f})",
        "timestamp": _utcnow().isoformat(),
        "data_snapshot": {
            "from_profile": profile_id,
            "to_profile": routed_profile,
            "confidence": confidence,
        },
    }

    return {
        "profile_id": routed_profile,
        "next_agent": "perception",
        "decisions": [decision],
    }
