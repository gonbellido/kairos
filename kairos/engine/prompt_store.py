"""Gestión de prompts de agentes. Lee de PostgreSQL, fallback a hardcoded defaults."""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kairos.db.models import AgentPromptModel

logger = logging.getLogger(__name__)

# ── Default hardcoded prompts (fallback si no hay en DB) ──

DEFAULT_PROMPTS = {
    "supervisor": {
        "description": "Router de mensajes — decide a qué perfil (coaching/comercial/financiero) enviar",
        "prompt_template": (
            "Eres un router de mensajes para un sistema multi-agente de coaching. "
            "Analiza el mensaje del usuario y determina:\n\n"
            "1. **Perfil más adecuado** para responder (coaching, comercial, financiero)\n"
            "2. **Intención** del mensaje\n"
            "3. **Confianza** en la clasificación (0-1)\n"
            "4. **Si requiere acción inmediata** (alerta)\n\n"
            "Considera:\n"
            "- coaching: preguntas existenciales, relaciones, desarrollo personal, liderazgo, equipo\n"
            "- comercial: ventas, objeciones, pricing, competencia, negociación\n"
            "- financiero: inversiones, riesgo, ahorro, planificación financiera, números\n\n"
            "Responde JSON:\n"
            '{{"profile_id": "coaching|comercial|financiero", "intention": "str", '
            '"confidence": 0.0-1.0, "requires_immediate_action": bool, "reasoning": "str"}}'
        ),
    },
    "analyst": {
        "description": "Analista de sesiones — revisa contexto y genera recomendaciones de intervención",
        "prompt_template": (
            "Eres un analista de sesiones de coaching. Revisa el contexto completo y genera:\n\n"
            "1. **Resumen del estado actual** del cliente basado en su perfil\n"
            "2. **Patrones relevantes** de experiencias previas similares\n"
            "3. **Recomendación de enfoque**: qué tipo de intervención usar\n"
            "4. **Señales a monitorear**: qué observar durante la interacción\n\n"
            "Basado en:\n"
            "- Clasificación de estado: {state}\n"
            "- Casos recuperados: {case_count} (score promedio: {avg_score})\n"
            "- Perfil del cliente: {client_info}\n"
            "- Patrones detectados: {patterns}\n\n"
            "Responde en JSON:\n"
            '{{"summary": "str", "recommended_approach": "str", '
            '"signals_to_monitor": ["str"], "risk_flags": ["str"]}}'
        ),
    },
    "validator": {
        "description": "Evaluador de respuestas — puntúa calidad, adherencia a impronta, seguridad",
        "prompt_template": (
            "You are a response evaluator. Score the following response on a scale 0-1 for:\n"
            "1. Overall quality\n"
            "2. Adherence to the profile's behavioral style (impronta)\n"
            "3. Factual consistency (if applicable)\n"
            "4. Safety (any harmful content?)\n"
            "5. Anti-patterns detected\n\n"
            "Profile: {profile}\n"
            "Impronta rules: {rules}\n"
            "User message: {message}\n"
            "Response: {response}\n\n"
            'Respond in JSON: {{"score": float, "impronta_adherence": float, '
            '"factual_consistency": float|null, "safety_check": bool, '
            '"feedback": "str", "anti_patterns_detected": ["str"]}}'
        ),
    },
    "classifier": {
        "description": "Clasificador de estado — detecta emoción, riesgo, urgencia, intención, tono",
        "prompt_template": (
            "Clasifica este mensaje de coaching en las siguientes categorías (0-1):\n"
            "- Riesgo (posibilidad de daño o crisis)\n"
            "- Emoción predominante (ansiedad, calma, frustración, esperanza, confusión, determinación, neutra)\n"
            "- Urgencia (necesidad inmediata de respuesta)\n"
            "- Intención (pregunta, queja, reflexión, solicitud, celebración)\n"
            "- Tono (formal, informal, emocional, analítico, confrontacional)\n\n"
            "Mensaje: {message}\n\n"
            'Responde SOLO JSON: {{"riesgo": float, "emocion": "str", '
            '"urgencia": float, "intencion": "str", "tono": "str"}}'
        ),
    },
    "synthesizer": {
        "description": "Sintetizador de cliente — extrae estado emocional, claridad, energía, insights",
        "prompt_template": (
            "Analiza esta conversación de coaching y sintetiza:\n"
            "1. Estado emocional actual (1 palabra)\n"
            "2. Claridad: 0-1\n"
            "3. Energía/motivación: 0-1\n"
            "4. Resistencia detectada: 0-1\n"
            "5. Patrones de lenguaje\n"
            "6. Insights clave\n"
            "7. Progreso vs sesión anterior\n\n"
            "Contexto de sesiones previas: {previous_state}\n"
            "Último mensaje: {last_message}\n"
            "Respuesta del coach: {coach_response}\n\n"
            'Responde JSON: {{"emocional": "str", "claridad": float, "energia": float, '
            '"resistencia": float, "patrones_lenguaje": ["str"], "insights": ["str"], '
            '"progreso": float, "notas": "str"}}'
        ),
    },
    "coach_assistant": {
        "description": "Asistente del coach — RAG sobre clientes y materiales",
        "prompt_template": (
            "Eres un asistente IA para un coach profesional. El coach te hace preguntas "
            "sobre sus clientes y sus materiales de coaching.\n\n"
            "## Reglas\n"
            "- Solo respondes sobre clientes que están en el contexto proporcionado\n"
            "- Si no tienes información suficiente, lo dices claramente\n"
            "- Usas un tono profesional y constructivo\n"
            "- Puedes hacer recomendaciones basadas en patrones detectados\n"
            "- Respondes en español\n\n"
            "## Clientes del coach\n{clientes_context}\n\n"
            "## Materiales relevantes\n{materiales_context}\n\n"
            "Responde a la pregunta del coach de forma clara y útil."
        ),
    },
}


class PromptStore:
    """Gestiona prompts de agentes desde PostgreSQL con fallback a defaults."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory
        self._cache: dict[str, str] = {}

    async def get(self, agent: str) -> str:
        """Obtiene el prompt template para un agente. Lee de DB, fallback a default."""
        if agent in self._cache:
            return self._cache[agent]

        try:
            async with self._sf() as session:
                result = await session.execute(
                    select(AgentPromptModel).where(AgentPromptModel.agent == agent)
                )
                row = result.scalar_one_or_none()
                if row and row.prompt_template:
                    self._cache[agent] = row.prompt_template
                    return row.prompt_template
        except Exception as e:
            logger.warning("Failed to read prompt '%s' from DB: %s", agent, e)

        # Fallback a default
        default = DEFAULT_PROMPTS.get(agent, {})
        prompt = default.get("prompt_template", "")
        self._cache[agent] = prompt
        return prompt

    async def set(self, agent: str, prompt_template: str) -> bool:
        """Guarda o actualiza un prompt en DB."""
        try:
            async with self._sf() as session:
                result = await session.execute(
                    select(AgentPromptModel).where(AgentPromptModel.agent == agent)
                )
                row = result.scalar_one_or_none()
                if row:
                    row.prompt_template = prompt_template
                    await session.commit()
                else:
                    from uuid import uuid4
                    desc = DEFAULT_PROMPTS.get(agent, {}).get("description", "")
                    row = AgentPromptModel(
                        id=uuid4().hex[:12],
                        agent=agent,
                        description=desc,
                        prompt_template=prompt_template,
                    )
                    session.add(row)
                    await session.commit()
                self._cache[agent] = prompt_template
                return True
        except Exception as e:
            logger.error("Failed to save prompt '%s' to DB: %s", agent, e)
            return False

    async def list_all(self) -> list[dict]:
        """Lista todos los prompts con metadata."""
        prompts = []
        for agent, default in DEFAULT_PROMPTS.items():
            entry = {
                "agent": agent,
                "description": default["description"],
                "prompt_template": await self.get(agent),
                "is_custom": agent in self._cache and self._cache[agent] != default["prompt_template"],
            }
            prompts.append(entry)
        return prompts

    async def reset(self, agent: str) -> bool:
        """Restaura un prompt a su valor default."""
        default = DEFAULT_PROMPTS.get(agent, {})
        return await self.set(agent, default.get("prompt_template", ""))

    async def seed_defaults(self):
        """Inserta prompts default en DB si no existen."""
        for agent, data in DEFAULT_PROMPTS.items():
            try:
                async with self._sf() as session:
                    exists = await session.execute(
                        select(AgentPromptModel).where(AgentPromptModel.agent == agent)
                    )
                    if not exists.scalar_one_or_none():
                        from uuid import uuid4
                        session.add(AgentPromptModel(
                            id=uuid4().hex[:12],
                            agent=agent,
                            description=data["description"],
                            prompt_template=data["prompt_template"],
                        ))
                await session.commit()
            except Exception:
                pass

    def invalidate_cache(self, agent: str | None = None):
        if agent:
            self._cache.pop(agent, None)
        else:
            self._cache.clear()
