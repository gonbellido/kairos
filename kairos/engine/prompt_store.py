import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kairos.db.models import AgentPromptModel
from kairos.engine.i18n import get_i18n, get_current_lang

logger = logging.getLogger(__name__)


class PromptStore:
    """Gestiona prompts de agentes desde PostgreSQL con fallback a i18n JSON defaults."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory
        self._cache: dict[tuple[str, str], str] = {}

    async def get(self, agent: str, lang: str | None = None) -> str:
        """Obtiene el prompt template para un agente. Lee de DB, fallback a default JSON."""
        lang = lang or get_current_lang()
        cache_key = (agent, lang)

        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            async with self._sf() as session:
                result = await session.execute(
                    select(AgentPromptModel).where(
                        AgentPromptModel.agent == agent,
                        AgentPromptModel.lang == lang
                    )
                )
                row = result.scalar_one_or_none()
                if row and row.prompt_template:
                    self._cache[cache_key] = row.prompt_template
                    return row.prompt_template
        except Exception as e:
            logger.warning("Failed to read prompt '%s' (%s) from DB: %s", agent, lang, e)

        # Fallback a default desde i18n files
        prompt = get_i18n(lang).prompt(agent)
        self._cache[cache_key] = prompt
        return prompt

    async def set(self, agent: str, prompt_template: str, lang: str | None = None) -> bool:
        """Guarda o actualiza un prompt en DB."""
        lang = lang or get_current_lang()
        try:
            async with self._sf() as session:
                result = await session.execute(
                    select(AgentPromptModel).where(
                        AgentPromptModel.agent == agent,
                        AgentPromptModel.lang == lang
                    )
                )
                row = result.scalar_one_or_none()
                if row:
                    row.prompt_template = prompt_template
                    await session.commit()
                else:
                    from uuid import uuid4
                    # Intentar obtener descripción de los defaults de i18n si no existe
                    desc = f"Prompt for {agent} ({lang})"
                    row = AgentPromptModel(
                        id=uuid4().hex[:12],
                        agent=agent,
                        description=desc,
                        prompt_template=prompt_template,
                        lang=lang
                    )
                    session.add(row)
                    await session.commit()
                self._cache[(agent, lang)] = prompt_template
                return True
        except Exception as e:
            logger.error("Failed to save prompt '%s' (%s) to DB: %s", agent, lang, e)
            return False

    async def list_all(self, lang: str | None = None) -> list[dict]:
        """Lista todos los prompts con metadata para el idioma actual."""
        lang = lang or get_current_lang()
        # En una implementación real, buscaríamos todos los agentes conocidos
        # Aquí dependemos de lo que haya en DB + los básicos que sabemos que existen
        known_agents = ["supervisor", "analyst", "validator", "classifier", "synthesizer", "coach_assistant"]

        prompts = []
        for agent in known_agents:
            entry = {
                "agent": agent,
                "lang": lang,
                "prompt_template": await self.get(agent, lang),
            }
            prompts.append(entry)
        return prompts

    async def reset(self, agent: str, lang: str | None = None) -> bool:
        """Restaura un prompt a su valor default (i18n JSON)."""
        lang = lang or get_current_lang()
        default_prompt = get_i18n(lang).prompt(agent)
        return await self.set(agent, default_prompt, lang)

    async def seed_defaults(self):
        """Inserta prompts default en DB si no existen para cada idioma soportado."""
        from kairos.engine.i18n import SUPPORTED_LANGS
        for lang in SUPPORTED_LANGS:
            i18n = get_i18n(lang)
            # Obtenemos el diccionario de prompts para este idioma
            prompts_dict = i18n._translations.get("prompts", {})
            for agent, template in prompts_dict.items():
                if not isinstance(template, str): continue
                try:
                    async with self._sf() as session:
                        exists = await session.execute(
                            select(AgentPromptModel).where(
                                AgentPromptModel.agent == agent,
                                AgentPromptModel.lang == lang
                            )
                        )
                        if not exists.scalar_one_or_none():
                            from uuid import uuid4
                            session.add(AgentPromptModel(
                                id=uuid4().hex[:12],
                                agent=agent,
                                description=f"Default {agent} prompt ({lang})",
                                prompt_template=template,
                                lang=lang
                            ))
                            await session.commit()
                except Exception as e:
                    logger.warning("Failed to seed prompt %s (%s): %s", agent, lang, e)

    def invalidate_cache(self, agent: str | None = None, lang: str | None = None):
        if agent and lang:
            self._cache.pop((agent, lang), None)
        else:
            self._cache.clear()
