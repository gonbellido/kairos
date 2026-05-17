import logging
from uuid import uuid4
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from kairos.core.client import ClientProfile, ClientObjective

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateClientRequest(BaseModel):
    coach_id: str = "default"
    nombre: str
    contexto: str = ""
    edad: int | None = None
    profile_id: str = "coaching"


@router.post("/clients/create")
async def create_client(req: Request, body: CreateClientRequest):
    store = req.app.state.runtime.client_store
    profile = ClientProfile(
        id=uuid4().hex,
        coach_id=body.coach_id,
        nombre=body.nombre,
        metadata={"edad": body.edad, "contexto": body.contexto, "notas": ""},
    )
    await store.upsert_profile(profile)
    return profile.model_dump(mode="json")


@router.post("/clients/{client_id}/objectives")
async def add_objective(req: Request, client_id: str, body: dict):
    store = req.app.state.runtime.client_store
    profile = store.get_profile(client_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Client not found")
    profile.objetivos.append(ClientObjective(
        id=uuid4().hex,
        titulo=body.get("titulo", ""),
        descripcion=body.get("descripcion", ""),
    ))
    await store.upsert_profile(profile)
    return profile.model_dump(mode="json")


@router.delete("/clients/{client_id}")
async def delete_client(req: Request, client_id: str):
    store = req.app.state.runtime.client_store
    ok = store.delete_profile(client_id)
    return {"ok": ok, "client_id": client_id}
