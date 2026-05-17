"""D4: Example plugin — Content safety filter."""

import logging
from kairos.plugins.base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class SafetyFilter(BasePlugin):
    name = "safety_filter"

    async def after_llm(self, response: str, context: dict) -> str:
        """Basic content safety: flag potentially harmful responses."""
        unsafe_patterns = [
            "suicidio", "autolesión", "violencia explícita",
        ]
        for pattern in unsafe_patterns:
            if pattern.lower() in response.lower():
                logger.warning(
                    "[SafetyFilter] Potentially unsafe content detected in response "
                    "(session=%s)", context.get("session_id", "?")
                )
                return (
                    "Lo siento, no puedo generar ese tipo de contenido. "
                    "Por favor, reformula tu pregunta o contacta a un profesional."
                )
        return response
