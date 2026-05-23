from datetime import datetime, timezone
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
from kairos.core.state import AgentState, Decision
from kairos.core.client import Alert
from kairos.memory.stores.client_store import ClientStore
from kairos.config import get_settings


THRESHOLDS = {
    "resistencia_alta": {"field": "resistencia", "min": 0.7, "tipo": "alta_resistencia", "nivel": "high"},
    "estancamiento": {"field": "claridad", "min": 0.0, "max": 0.2, "tipo": "estancamiento", "nivel": "medium"},
    "crisis_emocional": {"field": "emocional", "value": "crisis", "tipo": "crisis_emocional", "nivel": "urgent"},
    "baja_energia": {"field": "energia", "min": 0.0, "max": 0.2, "tipo": "baja_energia", "nivel": "low"},
}


async def alert_checker_node(
    state: AgentState,
    client_store: ClientStore | None = None,
) -> dict[str, Any]:
    client_id = state.get("context", {}).get("client_id", "")
    alerts_triggered: list[Alert] = []

    if client_id and client_store:
        profile = client_store.get_profile(client_id)
        if profile:
            estado = profile.estado_actual

            for name, cfg in THRESHOLDS.items():
                triggered = False
                field = cfg["field"]
                value = getattr(estado, field, None) if hasattr(estado, field) else None
                if value is None:
                    value = getattr(estado, field, "")

                if isinstance(value, (int, float)):
                    if cfg.get("min") is not None and cfg.get("max") is not None:
                        triggered = cfg["min"] <= value <= cfg["max"]
                    elif cfg.get("min") is not None:
                        triggered = value >= cfg["min"]
                elif isinstance(value, str):
                    triggered = value == cfg.get("value", "")

                if triggered:
                    alert = Alert(
                        tipo=cfg["tipo"],
                        nivel=cfg["nivel"],
                        accion="notify_coach" if cfg["nivel"] in ("high", "urgent") else "adjust_response",
                        mensaje=(
                            f'Cliente {profile.nombre}: {cfg["tipo"].replace("_", " ")} detectado ({field}={value})'
                            if profile.locale == 'es' else
                            f'Client {profile.nombre}: {cfg["tipo"].replace("_", " ").replace("alta resistencia", "high resistance").replace("estancamiento", "stagnation").replace("crisis emocional", "emotional crisis").replace("baja energia", "low energy")} detected ({field}={value})'
                        ),
                        cliente_id=client_id,
                        coach_id=profile.coach_id,
                    )
                    alerts_triggered.append(alert)
                    await client_store.store_alert(alert)

    decision: Decision = {
        "agent": "alert_checker",
        "action": "check",
        "reasoning": f"Checked alerts: {len(alerts_triggered)} triggered",
        "timestamp": _utcnow().isoformat(),
        "data_snapshot": {
            "alert_count": len(alerts_triggered),
            "alerts": [a.tipo for a in alerts_triggered],
        },
    }

    return {
        "decisions": [decision],
        "next_agent": "__end__",
    }
