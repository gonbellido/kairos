import json
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from kairos.core.client import (
    ClientProfile, ClientState, ClientInsight, ClientPattern,
    ClientProgress, SignalMetrics,
)
from kairos.config import get_settings

logger = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """Eres un sintetizador de sesiones de coaching. Analiza la conversación y extrae:

1. **Estado emocional** del cliente (neutral, positivo, negativo, ansioso, resistente, etc.)
2. **Claridad** (0-1): qué tan claro está el cliente sobre su situación
3. **Energía** (0-1): nivel de energía/compromiso
4. **Resistencia** (0-1): resistencia al cambio o a las preguntas
5. **Insights detectados** (lista): observaciones o revelaciones
6. **Patrones de lenguaje** (lista): frases/claves recurrentes
7. **Avances**: cambios positivos respecto a sesiones anteriores

Responde JSON:
{
  "estado_emocional": "str",
  "claridad": float,
  "energia": float,
  "resistencia": float,
  "insights": [{"tipo": "str", "contenido": "str"}],
  "patrones": [{"patron": "str", "frecuencia": int}],
  "avances": ["str"]
}
"""


class ClientSynthesizer:
    def __init__(self, llm: ChatOpenAI | None = None):
        settings = get_settings()
        self._llm = llm or ChatOpenAI(
            model=settings.evaluator_model,
            temperature=0.0,
            api_key=settings.llm_api_key,
        )

    async def synthesize(
        self,
        message: str,
        response: str,
        previous_profile: ClientProfile | None = None,
    ) -> dict:
        history = ""
        if previous_profile:
            history = (
                f"Estado previo: {previous_profile.estado_actual.model_dump(mode='json')}\n"
                f"Progreso: {previous_profile.progreso.score_global}\n"
                f"Patrones detectados: {[p.patron for p in previous_profile.patrones_detectados]}"
            )

        result = await self._llm.ainvoke([
            SystemMessage(content=SYNTHESIS_PROMPT),
            HumanMessage(content=(
                f"## Historial del cliente\n{history}\n\n"
                f"## Intervención del coach\n{response}\n\n"
                f"## Mensaje del cliente\n{message}"
            )),
        ])

        try:
            parsed = json.loads(
                result.content.strip()
                .removeprefix("```json").removesuffix("```").strip()
            )
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Synthesis parse failed, using defaults")
            parsed = {}

        return parsed

    def apply_synthesis(self, profile: ClientProfile, synthesis: dict) -> ClientProfile:
        if "estado_emocional" in synthesis:
            profile.estado_actual.emocional = synthesis["estado_emocional"]
        if "claridad" in synthesis:
            profile.estado_actual.claridad = float(synthesis["claridad"])
        if "energia" in synthesis:
            profile.estado_actual.energia = float(synthesis["energia"])
        if "resistencia" in synthesis:
            profile.estado_actual.resistencia = float(synthesis["resistencia"])

        for ins in synthesis.get("insights", []):
            if isinstance(ins, dict):
                profile.insights.append(ClientInsight(
                    tipo=ins.get("tipo", "observacion"),
                    contenido=ins.get("contenido", ""),
                    fuente="synthesis",
                ))

        existing = {p.patron for p in profile.patrones_detectados}
        for pat in synthesis.get("patrones", []):
            if isinstance(pat, dict):
                name = pat.get("patron", "")
                if name in existing:
                    for p in profile.patrones_detectados:
                        if p.patron == name:
                            p.frecuencia += 1
                            break
                else:
                    profile.patrones_detectados.append(ClientPattern(patron=name, frecuencia=1))

        profile.historial["mensajes"] = profile.historial.get("mensajes", 0) + 1

        signals = SignalMetrics(
            claridad=profile.estado_actual.claridad,
            apertura=1.0 - profile.estado_actual.resistencia,
            consistencia=profile.estado_actual.energia,
        )
        profile.progreso.senales = signals
        profile.progreso.score_global = round(
            (signals.claridad + signals.apertura + signals.accion + signals.consistencia) / 4, 2
        )

        return profile
