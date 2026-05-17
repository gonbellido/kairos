from datetime import datetime, timezone
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
from kairos.core.state import AgentState, Decision
from kairos.core.client import ClientProfile
from kairos.memory.stores.client_store import ClientStore
from kairos.engine.obsidian.writer import ObsidianWriter


async def obsidian_connector_node(
    state: AgentState,
    obsidian: ObsidianWriter,
    client_store: ClientStore | None = None,
) -> dict[str, Any]:
    client_id = state.get("context", {}).get("client_id", "")
    vault_path = str(obsidian._vault)

    try:
        obsidian.ensure_structure()
        obsidian.write_config_template()

        # Update client profile note if we have one
        profile: ClientProfile | None = None
        if client_id and client_store:
            profile = client_store.get_profile(client_id)

        if profile:
            obsidian.write_client_profile(profile)

            # Write alert if triggered
            eval_result = state.get("evaluation", {})
            if eval_result and eval_result.get("score", 1.0) < 0.4:
                from kairos.core.client import Alert as AlertModel
                from kairos.core.client import Alert
                alert = Alert(
                    tipo="bajo_score",
                    nivel="medium",
                    mensaje=f"Respuesta con score bajo ({eval_result.get('score', 0):.2f}) para {profile.nombre}",
                    cliente_id=client_id,
                )
                obsidian.write_alert(alert)

        # Update dashboard periodically (every N calls or via state flag)
        if state.get("context", {}).get("refresh_dashboard"):
            all_clients = await client_store.search_by_coach(state.get("profile_id", ""))
            obsidian.write_dashboard(all_clients)

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Obsidian sync failed: %s", e)

    decision: Decision = {
        "agent": "obsidian_connector",
        "action": "sync",
        "reasoning": f"Synced to vault at {vault_path}" + (f" for client {client_id}" if client_id else ""),
        "timestamp": _utcnow().isoformat(),
        "data_snapshot": {"vault": vault_path, "client_id": client_id},
    }

    return {
        "decisions": [decision],
        "next_agent": "__end__",
    }
