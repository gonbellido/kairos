from datetime import datetime, timezone
from pydantic import BaseModel, Field

_utcnow = lambda: datetime.now(tz=timezone.utc)


class SignalMetrics(BaseModel):
    claridad: float = 0.5
    accion: float = 0.5
    apertura: float = 0.5
    consistencia: float = 0.5


class ClientProgress(BaseModel):
    score_global: float = 0.0
    senales: SignalMetrics = Field(default_factory=SignalMetrics)
    ultima_actualizacion: datetime = Field(default_factory=lambda: _utcnow())


class ClientState(BaseModel):
    emocional: str = "neutral"
    claridad: float = 0.5
    energia: float = 0.5
    resistencia: float = 0.0


class ClientObjective(BaseModel):
    id: str = ""
    titulo: str
    descripcion: str = ""
    activo: bool = True
    creado_en: datetime = Field(default_factory=lambda: _utcnow())


class ClientInsight(BaseModel):
    tipo: str = "observacion"
    contenido: str
    fuente: str = "synthesis"
    timestamp: datetime = Field(default_factory=lambda: _utcnow())


class ClientPattern(BaseModel):
    patron: str
    frecuencia: int = 1
    ultima_deteccion: datetime = Field(default_factory=lambda: _utcnow())


class Alert(BaseModel):
    tipo: str = "info"
    nivel: str = "low"
    accion: str = "notify_coach"
    mensaje: str = ""
    cliente_id: str = ""
    coach_id: str = ""
    activa: bool = True
    creada_en: datetime = Field(default_factory=lambda: _utcnow())


class ClientProfile(BaseModel):
    id: str = ""
    coach_id: str = ""
    nombre: str = ""

    metadata: dict = Field(default_factory=lambda: {"edad": None, "contexto": "", "notas": ""})
    objetivos: list[ClientObjective] = Field(default_factory=list)

    estado_actual: ClientState = Field(default_factory=ClientState)
    historial: dict = Field(default_factory=lambda: {"sesiones": 0, "mensajes": 0})

    patrones_detectados: list[ClientPattern] = Field(default_factory=list)
    insights: list[ClientInsight] = Field(default_factory=list)

    progreso: ClientProgress = Field(default_factory=ClientProgress)
    alertas_activas: list[Alert] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: _utcnow())
    updated_at: datetime = Field(default_factory=lambda: _utcnow())
