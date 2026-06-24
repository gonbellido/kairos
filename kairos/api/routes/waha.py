"""F8: WAHA webhook endpoint — WhatsApp → Journey pipeline."""

import json
import logging
import os
from uuid import uuid4

from fastapi import APIRouter, Request
from sqlalchemy import select

from kairos.db.models import ClientSharedProfileModel, CoachModel
from kairos.db.session import create_session_factory
from kairos.engine.journey_engine import JourneyEngine
from kairos.engine.waha_connector import WAHAClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/waha", tags=["waha"])

_WAHA_URL = os.getenv("WAHA_API_URL", "http://waha:3000")
_WAHA_API_KEY = os.getenv("WAHA_API_KEY", "")
_DEFAULT_COACH_ID = os.getenv("WAHA_DEFAULT_COACH_ID", "")


def _get_waha():
    return WAHAClient(_WAHA_URL, _WAHA_API_KEY)


async def _resolve_waha_client(session: str, chat_id: str, from_number: str, coach_id: str) -> str:
    sf = create_session_factory()
    async with sf() as s:
        from sqlalchemy import text as sa_text
        result = await s.execute(
            sa_text("SELECT client_id FROM client_shared_profiles WHERE profile_data->>'waha_chat_id' = :chat_id")
            .bindparams(chat_id=chat_id)
        )
        row = result.first()
        if row:
            return row[0]

        # New WAHA client — create KAIROS client + shared_profile
        client_id = f"waha_{uuid4().hex[:10]}"
        profile = {"waha_chat_id": chat_id, "waha_phone": from_number, "waha_session": session}
        sp = ClientSharedProfileModel(
            id=uuid4().hex[:12],
            client_id=client_id,
            coach_id=coach_id,
            profile_data=profile,
        )
        s.add(sp)

        # Assign default journey
        coach_result = await s.execute(select(CoachModel).where(CoachModel.id == coach_id))
        coach = coach_result.scalars().first()
        journey_id = (coach.default_journey_id or "") if coach else ""
        if journey_id:
            je = JourneyEngine(sf)
            try:
                await je.assign_client(client_id, coach_id, journey_id)
            except Exception as e:
                logger.warning("WAHA client journey assign failed: %s", e)

        await s.commit()
        logger.info("WAHA client created: chat_id=%s client_id=%s", chat_id, client_id)
        return client_id


@router.post("/webhook")
async def waha_webhook(req: Request):
    try:
        body = await req.json()
    except Exception:
        return {"ok": False, "detail": "invalid json"}

    session = body.get("session", "default")
    chat_id = body.get("chatId", "")
    from_number = body.get("from", "")
    text = (body.get("body") or body.get("text") or "").strip()

    if not chat_id or not text:
        return {"ok": False, "detail": "missing chatId or text"}

    coach_id = _DEFAULT_COACH_ID
    if not coach_id:
        logger.warning("WAHA webhook: WAHA_DEFAULT_COACH_ID not configured")
        return {"ok": False, "detail": "coach not configured"}

    # Resolve client
    try:
        client_id = await _resolve_waha_client(session, chat_id, from_number, coach_id)
    except Exception as e:
        logger.error("WAHA client resolution failed: %s", e)
        return {"ok": False, "detail": str(e)}

    # Pipeline via fast_path (same as web chat)
    try:
        je = req.app.state.journey_engine
        from kairos.paths.fast_path import run as fast_run
        response_text = await fast_run(
            message=text,
            session_id=client_id,
            client_id=client_id,
            coach_id=coach_id,
            journey_engine=je,
        )
    except Exception as e:
        logger.error("WAHA fast_path failed: %s", e)
        return {"ok": False, "detail": "pipeline error"}

    # Send response via WAHA
    waha = _get_waha()
    ok = await waha.send_text(session, chat_id, response_text)
    if not ok:
        logger.warning("WAHA response not sent to %s", chat_id)

    return {"ok": True, "client_id": client_id}
