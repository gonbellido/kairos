from datetime import datetime, timezone
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
from kairos.core.state import AgentState, Decision
from kairos.core.client import ClientProfile, Alert
from kairos.memory.stores.client_store import ClientStore
from kairos.engine.client_synthesizer import ClientSynthesizer


async def client_synthesizer_node(
    state: AgentState,
    client_store: ClientStore,
    synthesizer: ClientSynthesizer,
) -> dict[str, Any]:
    client_id = state.get("context", {}).get("client_id", "")
    if not client_id:
        return {"next_agent": "__end__", "decisions": [{
            "agent": "client_synthesizer",
            "action": "skip",
            "reasoning": "No client_id in context",
            "timestamp": _utcnow().isoformat(),
            "data_snapshot": {},
        }]}

    profile = client_store.get_profile(client_id) or ClientProfile(
        id=client_id,
        coach_id=state.get("profile_id", ""),
        nombre=state.get("context", {}).get("client_name", ""),
    )

    synthesis = await synthesizer.synthesize(
        message=state["message"],
        response=state.get("llm_response", ""),
        previous_profile=profile,
    )

    updated = synthesizer.apply_synthesis(profile, synthesis)

    # Bump session count if this was a session start
    if state.get("context", {}).get("session_start"):
        updated.historial["sesiones"] = updated.historial.get("sesiones", 0) + 1

    await client_store.upsert_profile(updated)

    decision: Decision = {
        "agent": "client_synthesizer",
        "action": "update",
        "reasoning": f"Updated client {client_id}: {synthesis.get('estado_emocional', 'unknown')}",
        "timestamp": _utcnow().isoformat(),
        "data_snapshot": {
            "client_id": client_id,
            "emocion": synthesis.get("estado_emocional"),
            "insights": len(synthesis.get("insights", [])),
            "score_global": updated.progreso.score_global,
        },
    }

    return {
        "decisions": [decision],
        "next_agent": "alert_checker",
    }
