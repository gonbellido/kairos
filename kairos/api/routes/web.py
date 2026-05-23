import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from kairos.engine.i18n import get_i18n, get_current_lang

logger = logging.getLogger(__name__)

_tpl_dir = str(Path(__file__).resolve().parent.parent.parent / "web" / "templates")
_env = Environment(loader=FileSystemLoader(_tpl_dir), cache_size=0)
templates = Jinja2Templates(env=_env)
router = APIRouter()


def _get_lang(req: Request) -> str:
    """Detected language is stored in request.state by I18nMiddleware."""
    return getattr(req.state, "lang", get_current_lang())


def _render(req: Request, name: str, context: dict | None = None):
    """Render template with language injected."""
    ctx = dict(context or {})
    lang = _get_lang(req)
    ctx.setdefault("lang", lang)

    # Inject translation helper 't' into the context
    ctx["t"] = get_i18n(lang).t

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
    return _render(req, "login.html", {"title": _t("login_title"), "error": None})


@router.post("/login")
async def login_post(req: Request):
    data = await req.form()
    email = data.get("email")
    password = data.get("password")

    coach_db = req.app.state.coach_db
    coach = await coach_db.authenticate(email, password)

    if not coach:
        return _render(req, "login.html", {"title": _t("login_title"), "error": _t("login_error")})

    resp = RedirectResponse(url="/coach", status_code=303)
    token = await coach_db.create_session(coach["id"])
    resp.set_cookie(key="kairos_token", value=token, httponly=True, max_age=86400 * 7)

    # Persist coach language preference
    if coach.get("language"):
        resp.set_cookie(key="kairos_lang", value=coach["language"], httponly=True, max_age=86400 * 30)

    return resp


@router.get("/logout")
async def logout(req: Request):
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("kairos_token")
    return resp


async def _with_coach(req: Request):
    coach = await _get_coach(req)
    if not coach:
        return None, _redirect()
    return coach, None


# ── G: Coach Web ───────────────────────────────────────────────────

@router.get("/coach", response_class=HTMLResponse)
async def coach_dashboard(req: Request):
    coach, err = await _with_coach(req)
    if err:
        return err

    store = req.app.state.runtime.client_store
    clients = await store.search_by_coach(coach["id"])
    alerts = store.get_active_alerts(coach["id"])

    return _render(req, "coach/dashboard.html", {
        "title": _t("dashboard"),
        "coach": coach,
        "clients": clients,
        "alerts": alerts,
    })


@router.post("/coach/clients")
async def create_client(req: Request):
    coach, err = await _with_coach(req)
    if err:
        return err

    data = await req.form()
    nombre = data.get("nombre")
    if not nombre:
        return RedirectResponse(url="/coach", status_code=303)

    from kairos.core.client import ClientProfile
    client = ClientProfile(
        coach_id=coach["id"],
        nombre=nombre,
        metadata={
            "edad": data.get("edad"),
            "contexto": data.get("contexto"),
        }
    )
    # Default locale for new clients same as coach
    client.locale = coach.get("language", "es")

    store = req.app.state.runtime.client_store
    client_id = await store.upsert_profile(client)

    # C2: Initial onboarding journey if defined
    if coach.get("default_journey_id"):
        je = getattr(req.app.state, "journey_engine", None)
        if je:
            await je.assign_client(client_id, coach["id"], coach["default_journey_id"])

    return RedirectResponse(url=f"/coach/clients/{client_id}", status_code=303)


@router.get("/coach/clients/{client_id}", response_class=HTMLResponse)
async def client_detail(req: Request, client_id: str):
    coach, err = await _with_coach(req)
    if err:
        return err

    store = req.app.state.runtime.client_store
    profile = store.get_profile(client_id)
    if not profile or profile.coach_id != coach["id"]:
        return _redirect("Cliente no encontrado")

    sm = req.app.state.runtime.session_manager
    sessions = sm.list_by_client(client_id)

    # Journey progress
    je = getattr(req.app.state, "journey_engine", None)
    journey = None
    if je:
        journey = await je.get_client_journey(client_id)

    return _render(req, "coach/client_detail.html", {
        "title": profile.nombre,
        "coach": coach,
        "client": profile,
        "sessions": sessions,
        "journey": journey,
    })


@router.get("/coach/assistant", response_class=HTMLResponse)
async def coach_assistant(req: Request):
    coach, err = await _with_coach(req)
    if err:
        return err
    return _render(req, "coach/assistant.html", {
        "title": _t("assistant_title"), "coach": coach,
    })


@router.get("/coach/imprint", response_class=HTMLResponse)
async def coach_imprint(req: Request):
    coach, err = await _with_coach(req)
    if err:
        return err
    return _render(req, "coach/imprint.html", {
        "title": "Impronta", "coach": coach,
    })


@router.get("/coach/materials", response_class=HTMLResponse)
async def coach_materials(req: Request):
    coach, err = await _with_coach(req)
    if err:
        return err
    raw_store = req.app.state.runtime.raw_store
    materials = raw_store.list_by_filter(profile_id="coaching", client_id="", coach_id=coach["id"])
    return _render(req, "coach/materials.html", {
        "title": _t("materials_title"), "coach": coach, "materials": materials,
    })


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
                                try: emocion = line.split(":")[1].strip().strip('\"').strip("'")
                                except: pass
                        notas_clientes.append({"nombre": f.name, "id": "", "score": score, "emocion": emocion})
        if alertas_dir and alertas_dir.exists():
            for f in sorted(alertas_dir.glob("*.md")):
                notas_alertas.append({"archivo": f.name, "titulo": f.stem.replace("_", " ")[:60]})

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
        "title": _t("alerts_title"), "alerts": alerts, "client_map": client_map, "coach": coach,
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
        return _render(req, "client_login.html", {"title": "Acceso Cliente", "error": _t("errors.client_login_missing_token")})

    auth = _get_client_auth(req)
    profile = await auth.get_client_by_token(token)
    if not profile:
        return _render(req, "client_login.html", {"title": "Acceso Cliente", "error": _t("errors.client_login_invalid_token")})

    resp = RedirectResponse(url="/client/dashboard", status_code=303)
    resp.set_cookie(key="kairos_client_token", value=token, httponly=True, max_age=86400 * 30)

    # Persist client language preference if available in shared profile
    je = getattr(req.app.state, "journey_engine", None)
    if je:
        sp = await je.get_shared_profile(je._sf, profile.id)
        if sp and sp.get("locale"):
            resp.set_cookie(key="kairos_lang", value=sp["locale"], httponly=True, max_age=86400 * 30)

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
        "title": _t("prompts.settings_title"),
        "client": profile,
        "coach_name": coach_name,
        "profile_data": profile_data,
    })
