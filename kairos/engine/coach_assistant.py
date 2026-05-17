from datetime import datetime, timezone
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from kairos.config import get_settings
from kairos.config.llm_factory import create_llm

_utcnow = lambda: datetime.now(tz=timezone.utc)

COACH_SYSTEM_PROMPT = """Eres un asistente de coaching que ayuda al coach a analizar sus clientes.

Tienes acceso a la siguiente información de los clientes de este coach:

{clientes_context}

{materiales_context}

Reglas:
1. RESPUESTA EXCLUSIVA: Solo puedes responder sobre los clientes de este coach y sus datos.
2. Si te preguntan por información que no está en el contexto, di que no tienes esa información.
3. Puedes analizar patrones, progreso, estado emocional y alertas de los clientes.
4. Usa un tono profesional y analítico.
5. Si identificas algún patrón o recomendación, menciónalo.
6. Responde SIEMPRE en español.
"""


class CoachAssistant:
    def __init__(self, llm: ChatOpenAI | None = None, prompt_store=None):
        self._llm = llm or create_llm(temperature=0.3)
        self._prompt_store = prompt_store

    def _build_client_context(self, clients: list) -> str:
        if not clients:
            return "No hay clientes registrados."
        lines = ["## Clientes del coach"]
        for c in clients:
            s = c.estado_actual
            p = c.progreso
            patrones = ", ".join(pt.patron for pt in c.patrones_detectados[-3:]) if c.patrones_detectados else "ninguno"
            alertas = "⚠️ " + ", ".join(a.tipo for a in c.alertas_activas) if c.alertas_activas else "ninguna"
            lines.append(
                f"- {c.nombre}: estado={s.emocional}, claridad={s.claridad:.0%}, "
                f"energía={s.energia:.0%}, resistencia={s.resistencia:.0%}, "
                f"score global={p.score_global:.0%}, "
                f"sesiones={c.historial.get('sesiones', 0)}, "
                f"mensajes={c.historial.get('mensajes', 0)}, "
                f"patrones=[{patrones}], alertas=[{alertas}]"
            )
        return "\n".join(lines)

    def _build_materials_context(self, materials: list) -> str:
        if not materials:
            return "No hay materiales subidos por el coach."
        lines = ["## Materiales del coach (contenido relevantes)"]
        for m in materials:
            name = m.get("metadata", {}).get("original_name", "documento")
            preview = m.get("metadata", {}).get("preview", "")
            content_preview = m.get("content_preview", "") or preview
            tags = m.get("metadata", {}).get("tags", "")
            lines.append(f"- {name}: {content_preview[:300]} [tags: {tags}]")
        return "\n".join(lines)

    async def ask(self, question: str, clients: list, materials_context: str | None = None) -> str:
        clientes_ctx = self._build_client_context(clients)

        coach_prompt = COACH_SYSTEM_PROMPT
        if self._prompt_store:
            try:
                coach_prompt = await self._prompt_store.get("coach_assistant")
            except Exception:
                pass

        system = coach_prompt.format(
            clientes_context=clientes_ctx,
            materiales_context=materials_context or "No hay materiales relevantes para esta consulta.",
        )

        result = await self._llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=question),
        ])
        return result.content
