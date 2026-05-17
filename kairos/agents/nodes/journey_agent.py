import json
import logging
from typing import Any
from kairos.core.state import AgentState

logger = logging.getLogger(__name__)

async def journey_inject_node(state: AgentState, journey_engine) -> dict[str, Any]:
    """
    Si hay journey activo, enriquece el state con el prompt del agente actual.
    """
    if not journey_engine:
        return {}

    journey_context = state.get("journey_context")
    if not journey_context or journey_context.get("status") in ("completed", "not_started"):
        return {}

    client_id = state.get("context", {}).get("client_id")
    if not client_id:
        return {}

    try:
        # compose_agent_prompt(self, client_id, message, coach_name, language, memory_hits, coach_imprint)
        message = state.get("message", "")

        system_prompt = await journey_engine.compose_agent_prompt(
            client_id=client_id,
            message=message
        )

        if system_prompt:
            return {"journey_system_prompt": system_prompt}
    except Exception as e:
        logger.error(f"Error in journey_inject_node: {e}")

    return {}

async def journey_advance_node(state: AgentState, journey_engine) -> dict[str, Any]:
    """
    Procesa la respuesta del LLM para avanzar el journey y guardar datos.
    """
    if not journey_engine:
        return {}

    journey_context = state.get("journey_context")
    if not journey_context or journey_context.get("status") in ("completed", "not_started"):
        return {}

    client_id = state.get("context", {}).get("client_id")
    if not client_id:
        return {}

    llm_response = state.get("llm_response", "")
    if not llm_response:
        return {}

    try:
        # Get current agent data for validate_and_advance
        journey = journey_context.get("journey", {})
        agents = journey.get("agents", [])
        current_agent_id = journey_context.get("current_agent_id")
        agent_data = next((a for a in agents if a["id"] == current_agent_id), None)

        result = await journey_engine.validate_and_advance(
            client_id=client_id,
            llm_response=llm_response,
            agent_data=agent_data
        )

        # Detect collected data from JSON
        data = None
        try:
            clean = llm_response.strip()
            if clean.startswith("```"):
                # Handle cases where it might be ```json or just ```
                lines = clean.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean = "\n".join(lines).strip()
            data = json.loads(clean)
        except Exception:
            pass

        if data and isinstance(data, dict):
            structured = data.get("structured", {}) or {}
            collected = structured.get("collected_data")
            if not collected and isinstance(structured, dict):
                # Fallback to other fields as per journey_engine logic
                collected = {k: v for k, v in structured.items()
                             if v and not k.startswith("_") and not k.startswith("phase")}

            if collected:
                await journey_engine.save_collected(client_id, collected)

        updates = {}
        if result.get("advanced") or result.get("phase_completed"):
            old_phase = journey_context.get("current_phase_id")
            old_agent = journey_context.get("current_agent_id")

            new_context = await journey_engine.get_client_journey(client_id)
            updates["journey_context"] = new_context
            updates["journey_advanced"] = True
            updates["journey_advance_info"] = {
                "from_agent": old_agent,
                "to_agent": new_context.get("current_agent_id"),
                "phase": new_context.get("current_phase_id")
            }

        # If the LLM response was JSON, we want to use the message part for final_response
        if result.get("message") and result["message"] != llm_response:
            updates["final_response"] = result["message"]

        return updates

    except Exception as e:
        logger.error(f"Error in journey_advance_node: {e}")

    return {}
