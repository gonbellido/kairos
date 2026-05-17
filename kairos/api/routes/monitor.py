"""Admin Monitor — activity feed, journey status, agent traces, channel messages."""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from kairos.engine.activity import get_activity

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/monitor", tags=["monitor"])
_utcnow = lambda: datetime.now(tz=timezone.utc)
_traces: list = []


@router.get("/data")
async def monitor_data(req: Request):
    """Aggregated monitor data."""
    coach = None
    token = req.cookies.get("kairos_token")
    if token:
        coach = await req.app.state.coach_db.get_session(token)

    # Journey stats
    journeys_active = 0
    journeys_data = []
    if req.app.state.journey_engine:
        try:
            all_j = await req.app.state.journey_engine.list_journeys("default", full=False)
            journeys_data = all_j
            journeys_active = sum(1 for j in all_j if j.get("status") == "active")
        except Exception:
            pass

    # Active client journeys
    active_client_journeys = []
    if req.app.state.journey_engine:
        try:
            from kairos.db.models import ClientJourneyModel
            from sqlalchemy import select
            from kairos.db.session import create_session_factory
            sf = create_session_factory()
            async with sf() as s:
                result = await s.execute(
                    select(ClientJourneyModel).where(
                        ClientJourneyModel.status.in_(["in_progress", "not_started"])
                    ).order_by(ClientJourneyModel.last_interaction_at.desc()).limit(20)
                )
                for cj in result.scalars().all():
                    active_client_journeys.append({
                        "client_id": cj.client_id,
                        "journey_id": cj.journey_id,
                        "status": cj.status,
                        "progress_pct": cj.progress_pct,
                        "current_phase_id": cj.current_phase_id,
                        "last_interaction": cj.last_interaction_at.isoformat() if cj.last_interaction_at else "",
                    })
                await s.close()
        except Exception:
            pass

    # Journey events (recent)
    events = []
    try:
        from kairos.db.models import JourneyEventModel
        from sqlalchemy import select, desc
        from kairos.db.session import create_session_factory
        sf = create_session_factory()
        async with sf() as s:
            result = await s.execute(
                select(JourneyEventModel).order_by(desc(JourneyEventModel.created_at)).limit(50)
            )
            for ev in result.scalars().all():
                events.append({
                    "id": ev.id,
                    "client_id": ev.client_id,
                    "event_type": ev.event_type,
                    "phase_id": ev.phase_id,
                    "payload": ev.payload_data,
                    "ts": ev.created_at.isoformat() if ev.created_at else "",
                })
            await s.close()
    except Exception:
        pass

    return {
        "activity": get_activity(50),
        "traces": list(_traces)[:20],
        "journeys": {"total": len(journeys_data), "active": journeys_active, "list": journeys_data[:10]},
        "active_client_journeys": active_client_journeys,
        "events": events,
        "bots": len(getattr(req.app.state, "telegram_bots", {})),
    }
