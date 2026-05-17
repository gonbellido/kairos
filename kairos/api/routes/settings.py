"""Fase J: Settings API — notifications, onboarding, client journeys."""

import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from kairos.engine.coach_auth_pg import CoachDBA

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])

DEFAULT_NOTIFICATION = {
    "channels": {
        "email": {"enabled": True, "frequency": "daily"},
        "sms": {"enabled": False, "frequency": "immediate"},
        "push": {"enabled": True, "frequency": "immediate"},
        "whatsapp": {"enabled": False, "frequency": "daily"},
    },
    "quiet_hours": {"start": "22:00", "end": "08:00"},
}

DEFAULT_ONBOARDING = {
    "status": "incomplete",
    "processed_journeys_count": 0,
    "last_processed_at": None,
    "notify_journey_complete": True,
}


@router.get("/me")
async def get_settings(req: Request):
    token = req.cookies.get("kairos_token")
    if not token:
        return JSONResponse({"error": "No autorizado"}, status_code=401)
    coach_db: CoachDBA = req.app.state.coach_db
    coach = await coach_db.get_session(token)
    if not coach:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    notif = coach.get("notification_settings") or DEFAULT_NOTIFICATION
    onboard = coach.get("onboarding_meta") or DEFAULT_ONBOARDING

    return {
        "user_id": coach["id"],
        "notification": notif,
        "onboarding": onboard,
    }


@router.patch("/me")
async def update_settings(req: Request):
    token = req.cookies.get("kairos_token")
    if not token:
        return JSONResponse({"error": "No autorizado"}, status_code=401)
    coach_db: CoachDBA = req.app.state.coach_db
    coach = await coach_db.get_session(token)
    if not coach:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    body = await req.json()

    if "notification" in body:
        current = coach.get("notification_settings") or DEFAULT_NOTIFICATION
        if "channels" in body["notification"]:
            for ch, cfg in body["notification"]["channels"].items():
                if ch in current.get("channels", {}):
                    current["channels"][ch].update(cfg)
        if "quiet_hours" in body["notification"]:
            current["quiet_hours"] = body["notification"]["quiet_hours"]
        await coach_db.update_coach(coach["id"], notification_settings=current)

    if "onboarding" in body:
        current = coach.get("onboarding_meta") or DEFAULT_ONBOARDING
        current.update(body["onboarding"])
        await coach_db.update_coach(coach["id"], onboarding_meta=current)

    return {"ok": True}


@router.patch("/profile")
async def update_profile(req: Request):
    # Accept both coach token and client token
    token = req.cookies.get("kairos_token") or req.cookies.get("kairos_client_token")
    if not token:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    coach_db: CoachDBA = req.app.state.coach_db
    coach = await coach_db.get_session(token)
    if coach:
        # Coach updating their own profile
        body = await req.json()
        profile = body.get("profile", {})
        bio = profile.get("bio", "")
        if len(bio) > 200:
            return JSONResponse({"error": "Bio must be 200 characters or less"}, status_code=400)
        current = coach.get("profile_data") or {}
        current.update(profile)
        await coach_db.update_coach(coach["id"], profile_data=current)
        return {"ok": True, "profile": current}

    # Client token — update client profile in PostgreSQL (not Qdrant)
    from kairos.engine.client_auth import ClientAuth
    auth = ClientAuth(req.app.state.runtime.client_store)
    client_profile = await auth.get_client_by_token(token)
    if not client_profile:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    body = await req.json()
    profile_data = body.get("profile", {})

    # Save to client_shared_profiles in PostgreSQL
    je = getattr(req.app.state, "journey_engine", None)
    if je:
        sp = await je.get_shared_profile(je._sf, client_profile.id)
        if sp:
            await je.update_shared_profile(client_profile.id, profile_data=profile_data)
            return {"ok": True, "profile": profile_data}
        else:
            # Create shared profile if it doesn't exist
            await je.assign_client(client_profile.id, client_profile.coach_id, "")
            await je.update_shared_profile(client_profile.id, profile_data=profile_data)
            return {"ok": True, "profile": profile_data}

    return JSONResponse({"error": "Journey engine not available"}, status_code=500)


@router.get("/clients/{client_id}/journeys")
async def get_client_journeys(req: Request, client_id: str):
    token = req.cookies.get("kairos_token")
    if not token:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    je = getattr(req.app.state, "journey_engine", None)
    if not je:
        return {"journeys": []}

    cj = await je.get_client_journey(client_id)
    journeys = []
    if cj:
        journeys.append({
            "journey_id": cj.get("journey_id", ""),
            "journey_name": cj.get("journey", {}).get("name", ""),
            "steps_processed": len(cj.get("journey", {}).get("phases", [])),
            "progress_pct": cj.get("progress_pct", 0),
            "status": cj.get("status", ""),
            "current_phase": cj.get("current_phase_id", ""),
            "started_at": cj.get("started_at", ""),
            "last_interaction_at": cj.get("last_interaction_at", ""),
        })
    return {"journeys": journeys}
