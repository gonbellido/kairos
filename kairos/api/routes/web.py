import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from kairos.engine.i18n import get_i18n

logger = logging.getLogger(__name__)

_tpl_dir = str(Path(__file__).resolve().parent.parent.parent / "web" / "templates")
_env = Environment(loader=FileSystemLoader(_tpl_dir), cache_size=0)
templates = Jinja2Templates(env=_env)
router = APIRouter()


def _get_lang(req: Request) -> str:
    """Detect language from query param, cookie, or default."""
    qp = req.query_params.get("lang", "")
    if qp in ("es", "en"):
        return qp
    cookie = req.cookies.get("kairos_lang", "")
    if cookie in ("es", "en"):
        return cookie
    return "es"


def _render(req: Request, name: str, context: dict | None = None):
    """Render template with language injected."""
    ctx = dict(context or {})
    ctx.setdefault("lang", _get_lang(req))
    get_i18n(ctx["lang"])  # ensure i18n engine matches
    return templates.TemplateResponse(req, name, ctx)


def _t(key: str, **kwargs) -> str:
    return get_i18n().t(key, **kwargs)


# Inject i18n helpers into Jinja2 globals
_env.globals["t"] = _t


async def _get_coach(req: Request) -> dict | None:
    token = req.cookies.get("kairos_token")
    if not token:
        return None
    coach_db = req.app.state.coach_db
    return await coach_db.get_session(token)


def _redirect(msg: str = "No autorizado"):
    return RedirectResponse(url="/login", status_code=303)


# ── Login ──────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(req: Request):
    if await _get_coach(req):
        return RedirectResponse(url="/coach", status_code=303)
    return _render(req, "login.html", {"title": "Login", "error": None})


@router.post("/login")
async def login_post(req: Request):
    data = await req.form()
    email = data.get("email", "")
    password = data.get("password", "")
    coach_db = req.app.state.coach_db
    coach = await coach_db.authenticate(email, password)
    if not coach:
        return _render(req, "login.html", {"title": "Login", "error": "Email o contraseña incorrectos"})
    token = await coach_db.create_session(coach["id"])
    resp = RedirectResponse(url="/coach", status_code=303)
    resp.set_cookie(key="kairos_token", value=token, httponly=True, max_age=86400 * 7)
    return resp


@router.get("/logout")
async def logout(req: Request):
    token = req.cookies.get("kairos_token")
    if token:
        coach_db = req.app.state.coach_db
        await coach_db.delete_session(token)
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("kairos_token")
    return resp


# ── Admin ───────────────────────────────────────────────────────────

@router.get("/admin", response_class=HTMLResponse)
async def admin_page(req: Request):
    coach = await _get_coach(req)
    if not coach:
        return _redirect()
    if coach["role"] != "admin":
        return RedirectResponse(url="/coach", status_code=303)
    coach_db = req.app.state.coach_db
    coaches = await coach_db.list_coaches()
    journeys = []
    try:
        je = req.app.state.journey_engine
        logger.info("Admin page je=%s", type(je).__name__ if je else "None")
        if je:
            default_j = await je.list_journeys("default", full=False)
            coach_j = await je.list_journeys(coach["id"], full=False)
            journeys = default_j + coach_j
            logger.info("Admin page: default=%d coach=%d total=%d",
                        len(default_j), len(coach_j), len(journeys))
        else:
            logger.warning("Admin page: journey_engine is None")
    except Exception as e:
        logger.error("Admin page error loading journeys: %s", e, exc_info=True)
    return _render(req, "admin.html", {"title": "Admin", "coaches": coaches, "coach": coach, "journeys": journeys})


@router.post("/admin/coach/create")
async def admin_create_coach(req: Request):
    coach = await _get_coach(req)
    if not coach or coach["role"] != "admin":
        return _redirect()
    data = await req.form()
    try:
        coach_db = req.app.state.coach_db
        await coach_db.create_coach(data["email"], data["password"], data["name"], role="coach")
    except ValueError:
        pass
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/admin/coach/{coach_id}/delete")
async def admin_delete_coach(req: Request, coach_id: str):
    coach = await _get_coach(req)
    if not coach or coach["role"] != "admin":
        return _redirect()
    coach_db = req.app.state.coach_db
    await coach_db.delete_coach(coach_id)
    return RedirectResponse(url="/admin", status_code=303)


@router.put("/admin/coach/{coach_id}")
async def admin_update_coach(req: Request, coach_id: str):
    coach = await _get_coach(req)
    if not coach or coach["role"] != "admin":
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=403)
    body = await req.json()
    ok = await req.app.state.coach_db.update_coach(
        coach_id,
        name=body.get("name"),
        email=body.get("email"),
        role=body.get("role"),
        plan=body.get("plan"),
        language=body.get("language"),
        default_journey_id=body.get("default_journey_id", ""),
        telegram_token=body.get("telegram_token"),
        telegram_chat_id=body.get("telegram_chat_id"),
        telegram_bot_name=body.get("telegram_bot_name"),
        password=body.get("password") if body.get("password") else None,
    )
    return {"ok": ok is not None, "coach": ok}


# ── Admin: Channels ─────────────────────────────────────────────────

@router.get("/admin/channels", response_class=HTMLResponse)
async def admin_channels_page(req: Request):
    coach = await _get_coach(req)
    if not coach or coach["role"] != "admin":
        return _redirect()
    coach_db = req.app.state.coach_db
    coaches = await coach_db.list_coaches()
    bots = getattr(req.app.state, "telegram_bots", {})
    return _render(req, "admin_channels.html", {
        "title": "Canales",
        "coach": coach,
        "coaches": coaches,
        "telegram_bots": bots,
    })


@router.get("/admin/monitor", response_class=HTMLResponse)
async def admin_monitor_page(req: Request):
    coach = await _get_coach(req)
    if not coach or coach["role"] != "admin":
        return _redirect()
    return _render(req, "admin_monitor.html", {"title": "Monitor", "coach": coach})


@router.post("/admin/channels/telegram/{coach_id}/activate")
async def admin_activate_telegram(req: Request, coach_id: str):
    coach = await _get_coach(req)
    if not coach or coach["role"] != "admin":
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=403)

    coach_db = req.app.state.coach_db
    target = await coach_db.get_by_id(coach_id)
    if not target or not target.get("telegram_token"):
        return {"ok": False, "error": "Coach sin token Telegram configurado"}

    token = target["telegram_token"]
    runtime = req.app.state.runtime

    from kairos.engine.telegram_bot import KairosTelegramBot
    bot = KairosTelegramBot(token=token, runtime=runtime, coach_id=coach_id,
                            lang=target.get("language", "es"),
                            journey_engine=getattr(req.app.state, "journey_engine", None))
    bot.build_app()
    await bot._app.initialize()  # necesario para procesar updates

    # Set webhook — cada coach tiene su propio endpoint
    webhook_url = f"https://api.ether.care/telegram/webhook/{coach_id}"
    try:
        await bot._app.bot.set_webhook(url=webhook_url)
        bot_info = await bot._app.bot.get_me()
        bots = getattr(req.app.state, "telegram_bots", {})
        bots[coach_id] = bot
        req.app.state.telegram_bots = bots
        return {"ok": True, "username": bot_info.username, "name": bot_info.first_name, "webhook": webhook_url}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/admin/channels/telegram/{coach_id}/deactivate")
async def admin_deactivate_telegram(req: Request, coach_id: str):
    coach = await _get_coach(req)
    if not coach or coach["role"] != "admin":
        return JSONResponse({"ok": False}, status_code=403)
    bots = getattr(req.app.state, "telegram_bots", {})
    bot = bots.pop(coach_id, None)
    if bot and bot._app:
        try:
            await bot._app.bot.delete_webhook()
            await bot._app.stop()
        except Exception:
            pass
    req.app.state.telegram_bots = bots
    return {"ok": True}


# ── Admin: Prompt Management ───────────────────────────────────────

@router.get("/admin/prompts", response_class=HTMLResponse)
async def admin_prompts_page(req: Request):
    coach = await _get_coach(req)
    if not coach or coach["role"] != "admin":
        return _redirect()
    prompt_store = req.app.state.prompt_store
    prompts = await prompt_store.list_all()
    return _render(req, "admin_prompts.html", {
        "title": "Prompts",
        "coach": coach,
        "prompts": prompts,
    })


@router.put("/admin/prompts/{agent}")
async def admin_update_prompt(req: Request, agent: str):
    coach = await _get_coach(req)
    if not coach or coach["role"] != "admin":
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=403)
    body = await req.json()
    prompt_text = body.get("prompt_template", "")
    ok = await req.app.state.prompt_store.set(agent, prompt_text)
    req.app.state.prompt_store.invalidate_cache(agent)
    return {"ok": ok, "agent": agent}


@router.post("/admin/prompts/{agent}/reset")
async def admin_reset_prompt(req: Request, agent: str):
    coach = await _get_coach(req)
    if not coach or coach["role"] != "admin":
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=403)
    ok = await req.app.state.prompt_store.reset(agent)
    req.app.state.prompt_store.invalidate_cache(agent)
    return {"ok": ok, "agent": agent}


# ── Admin/Coach: Journey Management ────────────────────────────────

@router.get("/admin/journeys", response_class=HTMLResponse)
async def admin_journeys_page(req: Request):
    coach = await _get_coach(req)
    if not coach or coach["role"] != "admin":
        return _redirect()
    # Lazy init journey engine
    je = req.app.state.journey_engine
    if je is None:
        from kairos.engine.journey_engine import JourneyEngine
        from kairos.db.session import create_session_factory
        je = JourneyEngine(create_session_factory())
        req.app.state.journey_engine = je
        await je.seed_defaults()
    journeys = await je.list_journeys("default", full=True)
    coach_journeys = await je.list_journeys(coach["id"], full=True)
    all_journeys = journeys + [j for j in coach_journeys if j["id"] not in {x["id"] for x in journeys}]
    return _render(req, "admin_journeys.html", {"title": "Journeys", "coach": coach, "journeys": all_journeys})


@router.post("/api/v1/journeys")
async def create_journey(req: Request):
    coach = await _get_coach(req)
    if not coach or coach["role"] not in ("admin", "coach"):
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=403)
    body = await req.json()
    je = req.app.state.journey_engine
    j = await je.create_journey(coach_id=coach["id"], name=body.get("name", ""),
                                description=body.get("description", ""), objective=body.get("objective", ""),
                                profile_type=body.get("profile_type", "custom"),
                                language=body.get("language", coach.get("language", "es")))
    return {"ok": True, "journey": j}


@router.get("/api/v1/journeys/{journey_id}")
async def get_journey(req: Request, journey_id: str):
    coach = await _get_coach(req)
    if not coach: return JSONResponse({"ok": False}, status_code=403)
    je = req.app.state.journey_engine
    j = await je.get_journey(journey_id)
    return {"ok": True, "journey": j} if j else {"ok": False, "error": "Not found"}


@router.put("/api/v1/journeys/{journey_id}")
async def update_journey(req: Request, journey_id: str):
    coach = await _get_coach(req)
    if not coach: return JSONResponse({"ok": False}, status_code=403)
    body = await req.json()
    je = req.app.state.journey_engine
    j = await je.update_journey(journey_id, **body)
    return {"ok": True, "journey": j} if j else {"ok": False}


@router.delete("/api/v1/journeys/{journey_id}")
async def delete_journey_web(req: Request, journey_id: str):
    coach = await _get_coach(req)
    if not coach: return JSONResponse({"ok": False}, status_code=403)
    je = req.app.state.journey_engine
    ok = await je.delete_journey(journey_id)
    return {"ok": ok}


@router.post("/api/v1/journeys/{journey_id}/phases")
async def add_phase(req: Request, journey_id: str):
    coach = await _get_coach(req)
    if not coach: return JSONResponse({"ok": False}, status_code=403)
    body = await req.json()
    je = req.app.state.journey_engine
    p = await je.add_phase(journey_id, name=body.get("name", ""), objective=body.get("objective", ""),
                           description=body.get("description", ""), order_index=body.get("order_index", 0))
    return {"ok": True, "phase": p}


@router.put("/api/v1/journeys/{phase_id}/phases")
async def update_phase(req: Request, phase_id: str):
    coach = await _get_coach(req)
    if not coach: return JSONResponse({"ok": False}, status_code=403)
    body = await req.json()
    je = req.app.state.journey_engine
    p = await je.update_phase(phase_id, **body)
    return {"ok": True, "phase": p} if p else {"ok": False}


@router.put("/api/v1/journeys/phases/{phase_id}/reorder")
async def reorder_phase_web(req: Request, phase_id: str):
    coach = await _get_coach(req)
    if not coach: return JSONResponse({"ok": False}, status_code=403)
    body = await req.json()
    je = req.app.state.journey_engine
    ok = await je.reorder_phase(phase_id, direction=body.get("direction", "up"))
    return {"ok": ok}


@router.post("/api/v1/journeys/{journey_id}/agents")
async def add_agent(req: Request, journey_id: str):
    coach = await _get_coach(req)
    if not coach: return JSONResponse({"ok": False}, status_code=403)
    body = await req.json()
    je = req.app.state.journey_engine
    a = await je.add_agent(journey_id, phase_id=body.get("phase_id", ""), name=body.get("name", ""),
                           role=body.get("role", ""), goal=body.get("goal", ""),
                           system_prompt=body.get("system_prompt", ""), instructions=body.get("instructions", ""),
                           order_index=body.get("order_index", 0))
    return {"ok": True, "agent": a}


@router.put("/api/v1/journeys/agents/{agent_id}")
async def update_agent(req: Request, agent_id: str):
    coach = await _get_coach(req)
    if not coach: return JSONResponse({"ok": False}, status_code=403)
    body = await req.json()
    je = req.app.state.journey_engine
    a = await je.update_agent(agent_id, **body)
    return {"ok": True, "agent": a} if a else {"ok": False}


# ── Coach: Assign journey to client ────────────────────────────────

@router.post("/api/v1/clients/{client_id}/journey")
async def assign_journey(req: Request, client_id: str):
    coach = await _get_coach(req)
    if not coach: return JSONResponse({"ok": False}, status_code=403)
    body = await req.json()
    journey_id = body.get("journey_id", "")
    je = req.app.state.journey_engine
    cj = await je.assign_client(client_id, coach["id"], journey_id)
    return {"ok": True, "client_journey": cj} if cj else {"ok": False, "error": "Journey not found"}


@router.get("/api/v1/clients/{client_id}/journey")
async def get_client_journey(req: Request, client_id: str):
    coach = await _get_coach(req)
    if not coach: return JSONResponse({"ok": False}, status_code=403)
    je = req.app.state.journey_engine
    cj = await je.get_client_journey(client_id)
    return {"ok": True, "client_journey": cj} if cj else {"ok": False, "error": "No journey assigned"}


@router.post("/api/v1/clients/{client_id}/journey/advance")
async def advance_client_journey(req: Request, client_id: str):
    coach = await _get_coach(req)
    if not coach: return JSONResponse({"ok": False}, status_code=403)
    je = req.app.state.journey_engine
    cj = await je.advance_client(client_id)
    return {"ok": True, "client_journey": cj} if cj else {"ok": False}


# ── Client: Journey state ──────────────────────────────────────────

@router.get("/api/v1/client/journey")
async def client_get_journey(req: Request):
    client_data = await _get_client(req)
    if not client_data:
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=401)
    je = req.app.state.journey_engine
    cj = await je.get_client_journey(client_data["id"])
    return {"ok": True, "client_journey": cj} if cj else {"ok": False, "error": "No journey"}


# ── Coach Routes ───────────────────────────────────────────────────

async def _with_coach(req: Request):
    coach = await _get_coach(req)
    if not coach:
        return None, _redirect()
    return coach, None


# ── Coach: Imprint Profile ────────────────────────────────────────

@router.get("/coach/imprint", response_class=HTMLResponse)
async def coach_imprint_page(req: Request):
    coach, err = await _with_coach(req)
    if err:
        return err
    return _render(req, "coach/imprint.html", {"title": "Impronta", "coach": coach})


@router.get("/coach/settings", response_class=HTMLResponse)
async def coach_settings_page(req: Request):
    coach, err = await _with_coach(req)
    if err:
        return err
    # Get available journeys for default selection
    journeys = []
    je = req.app.state.journey_engine
    if je:
        try:
            journeys = await je.list_journeys("default", full=False)
            cj = await je.list_journeys(coach["id"], full=False)
            journeys = journeys + cj
        except Exception:
            pass
    return _render(req, "settings.html", {"title": "Configuración", "coach": coach, "journeys": journeys})


@router.put("/coach/imprint")
async def coach_update_imprint(req: Request):
    coach = await _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False}, status_code=403)
    body = await req.json()
    impronta = body.get("impronta", {})
    coach_db = req.app.state.coach_db
    await coach_db.update_coach(coach["id"], impronta_data=impronta)
    return {"ok": True, "impronta": impronta}


@router.put("/coach/default-journey")
async def coach_set_default_journey(req: Request):
    coach = await _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False}, status_code=403)
    body = await req.json()
    journey_id = body.get("journey_id", "")
    coach_db = req.app.state.coach_db
    await coach_db.update_coach(coach["id"], default_journey_id=journey_id)
    return {"ok": True, "journey_id": journey_id}


@router.get("/coach", response_class=HTMLResponse)
async def coach_dashboard(req: Request):
    coach, err = await _with_coach(req)
    if err:
        return err
    store = req.app.state.runtime.client_store
    coach_map = {}
    journeys = []
    if coach["role"] == "admin":
        clients = await store.list_all()
        coach_db = req.app.state.coach_db
        coaches = await coach_db.list_coaches()
        coach_map = {c["id"]: c["name"] for c in coaches}
    else:
        clients = await store.search_by_coach(coach["id"])

    # Journey list for assignment
    if req.app.state.journey_engine:
        try:
            journeys = await req.app.state.journey_engine.list_journeys("default", full=False)
            coach_j = await req.app.state.journey_engine.list_journeys(coach["id"], full=False)
            journeys = journeys + coach_j
        except Exception:
            pass

    # Check which clients have journeys assigned
    client_journeys = {}
    if req.app.state.journey_engine:
        for c in clients:
            try:
                cj = await req.app.state.journey_engine.get_client_journey(c.id)
                if cj:
                    client_journeys[c.id] = cj
            except Exception:
                pass

    # Count alerts
    alerts_total = sum(1 for c in clients if c.alertas_activas)

    return _render(req, "coach/dashboard.html", {
        "title": "Dashboard", "clients": clients, "coach": coach, "coach_map": coach_map,
        "journeys": journeys, "client_journeys": client_journeys, "alerts_count": alerts_total,
    })


@router.get("/coach/client/{client_id}", response_class=HTMLResponse)
async def coach_client_detail(req: Request, client_id: str):
    coach, err = await _with_coach(req)
    if err:
        return err
    store = req.app.state.runtime.client_store
    profile = store.get_profile(client_id)
    if not profile:
        return HTMLResponse("Client not found", status_code=404)
    sm = req.app.state.runtime.session_manager
    sessions = sm.list_by_client(client_id)
    vault_name = Path(getattr(req.app.state.runtime, "_vault_path", "")).name if getattr(req.app.state.runtime, "_vault_path", None) else ""

    # Journey data
    journeys = []
    client_journey = None
    je = req.app.state.journey_engine
    if je is None:
        from kairos.engine.journey_engine import JourneyEngine
        from kairos.db.session import create_session_factory
        je = JourneyEngine(create_session_factory())
        req.app.state.journey_engine = je
        await je.seed_defaults()
    try:
        journeys = await je.list_journeys("default", full=False)
        c_j = await je.list_journeys(coach["id"], full=False)
        journeys = journeys + c_j
        client_journey = await je.get_client_journey(client_id)
    except Exception as e:
        logger.warning("Journey load failed for client %s: %s", client_id, e)

    # Merge journey collected_data into profile.metadata for display
    vital_fields_data = {}
    if client_journey:
        try:
            import json as _json
            from kairos.engine.vital_fields import extract_vital_fields, VITAL_FIELDS as VF_REGISTRY
            collected = client_journey.get("collected_data", {}) or {}
            if isinstance(collected, str):
                try: collected = _json.loads(collected)
                except: collected = {}
            sp = client_journey.get("shared_profile", {}) or {}
            sp_data = sp.get("profile_data", {}) or {}
            # Prefer vital_fields stamped by save_collected
            vital_fields_data = sp_data.get("vital_fields", {}) or extract_vital_fields({**sp_data, **collected})
            merged_profile = {**sp_data, **{k: v for k, v in collected.items() if v and not k.startswith("_")}}
            if merged_profile:
                profile.metadata["journey_data"] = {k: v for k, v in merged_profile.items() if k != "vital_fields"}
        except Exception:
            pass

    return _render(req, "coach/client_detail.html", {
        "title": profile.nombre, "client": profile, "sessions": sessions,
        "vault_name": vault_name, "coach": coach,
        "journeys": journeys, "client_journey": client_journey,
        "vital_fields": vital_fields_data,
    })


@router.get("/coach/chat/{client_id}", response_class=HTMLResponse)
async def coach_chat_page(req: Request, client_id: str):
    coach, err = await _with_coach(req)
    if err:
        return err
    store = req.app.state.runtime.client_store
    profile = store.get_profile(client_id)
    if not profile:
        return HTMLResponse("Client not found", status_code=404)

    je = req.app.state.journey_engine
    journey_info = None
    collected_data = {}
    try:
        cj = await je.get_client_journey(client_id)
        if cj:
            journey = cj.get("journey", {})
            phases = journey.get("phases", [])
            agents = journey.get("agents", [])
            current_phase = next((p for p in phases if p["id"] == cj.get("current_phase_id")), {})
            current_agent = next((a for a in agents if a["id"] == cj.get("current_agent_id")), {})
            sp = cj.get("shared_profile", {}) or {}
            collected_data = cj.get("collected_data", {}) or {}
            if isinstance(collected_data, str):
                import json as _json
                try: collected_data = _json.loads(collected_data)
                except: collected_data = {}
            journey_info = {
                "name": journey.get("name"),
                "current_phase": current_phase.get("name"),
                "current_agent": current_agent.get("name"),
                "progress_pct": cj.get("progress_pct", 0),
                "goal": current_agent.get("goal") or current_phase.get("objective"),
                "allowed_tags": current_agent.get("allowed_tags", []),
                "tasks": [t for t in (sp.get("tasks_data") or []) if t.get("status") != "completed"][:5],
            }
    except Exception as e:
        logger.warning("Journey load failed for coach chat %s: %s", client_id, e)

    return _render(req, "coach/chat.html", {
        "title": f"Chat — {profile.nombre}", "client": profile, "coach": coach,
        "profile_id": "coaching", "journey_info": journey_info,
        "collected_data": {k: v for k, v in collected_data.items() if v and not k.startswith("_")},
    })


@router.post("/coach/client/{client_id}/delete")
async def coach_delete_client(req: Request, client_id: str):
    coach = await _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False}, status_code=403)
    store = req.app.state.runtime.client_store
    profile = store.get_profile(client_id)
    if not profile:
        return JSONResponse({"ok": False, "error": "Not found"}, status_code=404)
    if coach["role"] != "admin" and profile.coach_id != coach["id"]:
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=403)
    ok = store.delete_profile(client_id)
    return {"ok": ok}


@router.put("/coach/client/{client_id}/profile")
async def coach_update_client_profile(req: Request, client_id: str):
    coach = await _get_coach(req)
    if not coach:
        return JSONResponse({"ok": False}, status_code=403)
    store = req.app.state.runtime.client_store
    profile = store.get_profile(client_id)
    if not profile:
        return JSONResponse({"ok": False, "error": "Not found"}, status_code=404)
    if coach["role"] != "admin" and profile.coach_id != coach["id"]:
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=403)

    body = await req.json()
    new_profile = body.get("profile", {})
    pdata = dict(profile.metadata or {})
    pdata["profile_data"] = new_profile
    profile.metadata = pdata
    await store.upsert_profile(profile)
    return {"ok": True}


@router.post("/coach/client/create")
async def coach_create_client(req: Request):
    coach, err = await _with_coach(req)
    if err:
        return err
    from uuid import uuid4
    from kairos.core.client import ClientProfile
    body = await req.json()
    store = req.app.state.runtime.client_store
    profile = ClientProfile(
        id=uuid4().hex,
        coach_id=coach["id"],
        nombre=body.get("nombre", "Cliente"),
        metadata={"edad": body.get("edad"), "contexto": body.get("contexto", ""), "notas": "",
                  "access_token": uuid4().hex[:12]},
    )
    await store.upsert_profile(profile)

    # Auto-assign default journey if coach has one
    je = getattr(req.app.state, "journey_engine", None)
    default_journey_id = coach.get("default_journey_id", "")
    if je and default_journey_id:
        try:
            await je.assign_client(profile.id, coach["id"], default_journey_id)
        except Exception:
            pass
    elif je:
        try:
            default_j = await je.list_journeys("default", full=False)
            coach_j = await je.list_journeys(coach["id"], full=False) if coach["id"] != "default" else []
            all_j = default_j + coach_j
            fallback = next((j for j in all_j if j.get("profile_type") == "coaching"), all_j[0] if all_j else None)
            if fallback:
                await je.assign_client(profile.id, coach["id"], fallback["id"])
        except Exception:
            pass

    return JSONResponse(profile.model_dump(mode="json"))


@router.get("/coach/assistant", response_class=HTMLResponse)
async def coach_assistant_page(req: Request):
    coach, err = await _with_coach(req)
    if err:
        return err
    return _render(req, "coach/assistant.html", {"title": "Asistente", "coach": coach})


@router.get("/coach/materials", response_class=HTMLResponse)
async def coach_materials(req: Request):
    coach, err = await _with_coach(req)
    if err:
        return err
    return _render(req, "coach/materials.html", {"title": "Materiales", "coach": coach})


@router.get("/coach/obsidian", response_class=HTMLResponse)
@router.get("/coach/obsidian", response_class=HTMLResponse)
async def coach_obsidian(req: Request):
    coach, err = await _with_coach(req)
    if err:
        return err
    from pathlib import Path as P
    from kairos.config import get_settings
    settings = get_settings()
    vault = settings.obsidian_vault
    vault_ok = bool(vault and P(vault).exists())

    # ── Vault files ──
    notas_clientes, notas_alertas = [], []
    if vault_ok:
        base = P(vault) / "KAIROS"
        clientes_dir = base / "Clientes"
        alertas_dir = base / "Alertas"
        if clientes_dir and clientes_dir.exists():
            for f in sorted(clientes_dir.iterdir()):
                if f.is_dir():
                    md = f / f"{f.name}.md"
                    if md.exists():
                        content = md.read_text(encoding="utf-8")
                        score = "?"; emocion = "?"
                        for line in content.split("\n"):
                            if "score_global:" in line:
                                try: score = str(round(float(line.split(":")[1].strip()) * 100))
                                except: pass
                            if "emocion:" in line:
                                try: emocion = line.split(":")[1].strip().strip('"').strip("'")
                                except: pass
                        notas_clientes.append({"nombre": f.name, "id": "", "score": score, "emocion": emocion})
        if alertas_dir and alertas_dir.exists():
            for f in sorted(alertas_dir.glob("*.md")):
                notas_alertas.append({"archivo": f.name, "titulo": f.stem.replace("_", " ")[:60]})

    # ── Qdrant documents (SIEMPRE se muestran) ──
    raw_store = req.app.state.runtime.raw_store
    client_store = req.app.state.runtime.client_store

    coach_materials = raw_store.list_by_filter(
        profile_id="coaching", client_id="", coach_id=coach["id"], limit=50
    )

    clients = await client_store.search_by_coach(coach["id"])
    client_docs = []
    for c in clients[:20]:
        docs = raw_store.list_by_filter(
            profile_id="coaching", client_id=c.id, coach_id=coach["id"], limit=20
        )
        for d in docs:
            d["_client_name"] = c.nombre
            client_docs.append(d)

    return _render(req, "coach/obsidian.html", {
        "title": "Obsidian",
        "configurado": vault_ok,
        "coach": coach,
        "vault_path": str(P(vault)) if vault_ok else "",
        "obsidian_vault": f"obsidian://open?vault={P(vault).name}" if vault_ok else "",
        "vault_name": P(vault).name if vault_ok else "",
        "stats": {
            "clientes": len(notas_clientes),
            "alertas": len(notas_alertas),
            "materiales": len(coach_materials),
            "docs_cliente": len(client_docs),
        },
        "notas_clientes": notas_clientes,
        "notas_alertas": notas_alertas,
        "coach_materials": coach_materials,
        "client_docs": client_docs,
    })


@router.get("/coach/alerts", response_class=HTMLResponse)
async def coach_alerts(req: Request):
    coach, err = await _with_coach(req)
    if err:
        return err
    store = req.app.state.runtime.client_store
    alerts = store.get_active_alerts(coach["id"])
    coaches_list = await store.search_by_coach(coach["id"])
    client_map = {c.id: c.nombre for c in coaches_list}
    return _render(req, "coach/alerts.html", {
        "title": "Alertas", "alerts": alerts, "client_map": client_map, "coach": coach,
    })


# ── H: Client Web ──────────────────────────────────────────────────

from kairos.engine.client_auth import ClientAuth


def _get_client_auth(req: Request) -> ClientAuth:
    return ClientAuth(req.app.state.runtime.client_store)


async def _get_client(req: Request) -> dict | None:
    token = req.cookies.get("kairos_client_token")
    if not token:
        return None
    auth = _get_client_auth(req)
    profile = await auth.get_client_by_token(token)
    if profile:
        return profile.model_dump(mode="json")
    return None


@router.get("/", response_class=HTMLResponse)
async def landing_page(req: Request):
    return _render(req, "landing.html", {"title": "Inicio"})


@router.get("/client/login", response_class=HTMLResponse)
async def client_login_page(req: Request):
    if await _get_client(req):
        return RedirectResponse(url="/client/dashboard", status_code=303)
    return _render(req, "client_login.html", {"title": "Acceso Cliente", "error": None})


@router.post("/client/login")
async def client_login_post(req: Request):
    data = await req.form()
    token = data.get("token", "").strip()
    if not token:
        return _render(req, "client_login.html", {"title": "Acceso Cliente", "error": "Ingresa tu código de acceso"})

    auth = _get_client_auth(req)
    profile = await auth.get_client_by_token(token)
    if not profile:
        return _render(req, "client_login.html", {"title": "Acceso Cliente", "error": "Código no válido. Verifica con tu coach."})

    resp = RedirectResponse(url="/client/dashboard", status_code=303)
    resp.set_cookie(key="kairos_client_token", value=token, httponly=True, max_age=86400 * 30)
    return resp


@router.get("/client/logout")
async def client_logout(req: Request):
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("kairos_client_token")
    return resp


@router.get("/client/dashboard", response_class=HTMLResponse)
async def client_dashboard(req: Request):
    client_data = await _get_client(req)
    if not client_data:
        return RedirectResponse(url="/client/login", status_code=303)

    from kairos.core.client import ClientProfile
    profile = ClientProfile(**client_data)

    sm = req.app.state.runtime.session_manager
    sessions = sm.list_by_client(profile.id)

    # Fase I: Journey data for client dashboard
    journey_info = None
    if req.app.state.journey_engine:
        try:
            cj = await req.app.state.journey_engine.get_client_journey(profile.id)
            if cj:
                journey = cj.get("journey", {})
                phases = journey.get("phases", [])
                current_phase = next((p for p in phases if p["id"] == cj.get("current_phase_id")), {})
                agents = journey.get("agents", [])
                current_agent = next((a for a in agents if a["id"] == cj.get("current_agent_id")), {})
                sp = cj.get("shared_profile", {}) or {}
                journey_info = {
                    "name": journey.get("name"),
                    "objective": journey.get("objective"),
                    "current_phase": current_phase.get("name"),
                    "current_agent": current_agent.get("name"),
                    "progress_pct": cj.get("progress_pct", 0),
                    "status": cj.get("status"),
                    "phases_count": len(phases),
                    "tasks": [t for t in (sp.get("tasks_data") or []) if t.get("status") != "completed"][:5],
                    "checkpoints": sp.get("checkpoints_data", [])[:10],
                }
        except Exception:
            pass

    return _render(req, "client_dashboard.html", {
        "title": profile.nombre,
        "client": profile,
        "sessions": sessions,
        "journey": journey_info,
    })


@router.get("/client/chat", response_class=HTMLResponse)
async def client_chat_page(req: Request):
    client_data = await _get_client(req)
    if not client_data:
        return RedirectResponse(url="/client/login", status_code=303)

    from kairos.core.client import ClientProfile
    profile = ClientProfile(**client_data)

    # Journey context
    journey_info = None
    if req.app.state.journey_engine:
        try:
            cj = await req.app.state.journey_engine.get_client_journey(profile.id)
            if cj:
                journey = cj.get("journey", {})
                phases = journey.get("phases", [])
                current_phase = next((p for p in phases if p["id"] == cj.get("current_phase_id")), {})
                agents = journey.get("agents", [])
                current_agent = next((a for a in agents if a["id"] == cj.get("current_agent_id")), {})
                sp = cj.get("shared_profile", {}) or {}
                journey_info = {
                    "name": journey.get("name"),
                    "current_phase": current_phase.get("name"),
                    "current_agent": current_agent.get("name"),
                    "progress_pct": cj.get("progress_pct", 0),
                    "status": cj.get("status"),
                    "goal": current_agent.get("goal") or current_phase.get("objective"),
                    "tasks": [t for t in (sp.get("tasks_data") or []) if t.get("status") != "completed"][:5],
                }
        except Exception:
            pass

    return _render(req, "client_chat.html", {
        "title": "Chat — " + profile.nombre,
        "client": profile,
        "profile_id": "coaching",
        "journey": journey_info,
    })


@router.get("/client/settings", response_class=HTMLResponse)
async def client_settings_page(req: Request):
    client_data = await _get_client(req)
    if not client_data:
        return RedirectResponse(url="/client/login", status_code=303)
    from kairos.core.client import ClientProfile
    profile = ClientProfile(**client_data)

    # Read profile from PostgreSQL (client_shared_profiles), not Qdrant
    profile_data = {}
    je = getattr(req.app.state, "journey_engine", None)
    if je:
        try:
            sp = await je.get_shared_profile(je._sf, profile.id)
            if sp:
                profile_data = sp.get("profile_data", {}) or {}
        except Exception:
            pass

    coach_name = ""
    try:
        coach = await req.app.state.coach_db.get_by_id(profile.coach_id)
        if coach:
            coach_name = coach.get("name", "")
    except Exception:
        pass

    return _render(req, "client_settings.html", {
        "title": "Configuración",
        "client": profile,
        "coach_name": coach_name,
        "profile_data": profile_data,
    })
