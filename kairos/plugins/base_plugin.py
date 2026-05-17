from abc import ABC, abstractmethod
from typing import Any

from kairos.core.memory import CaseMemory


class BasePlugin(ABC):
    """D4: Base class for KAIROS plugins with hook points for the entire pipeline."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    # ── Hook: before prompt is built ──
    async def before_prompt(self, context: dict) -> dict:
        """Modify the prompt context before building. Return modified context."""
        return context

    # ── Hook: after LLM generates response ──
    async def after_llm(self, response: str, context: dict) -> str:
        """Post-process LLM output. Return (possibly modified) response text."""
        return response

    # ── Hook: before storing case in memory ──
    async def before_store(self, case: CaseMemory, context: dict) -> CaseMemory:
        """Modify or enrich the case before it's stored in Qdrant."""
        return case

    # ── Hook: after validation / evaluation ──
    async def after_validate(self, evaluation: dict, context: dict) -> dict:
        """Post-process evaluation results before they are stored."""
        return evaluation

    # ── Hook: before sending final response to user ──
    async def before_response(self, response: str, context: dict) -> str:
        """Final post-processing before the response reaches the user."""
        return response

    # ── Hook: on session end (logging, analytics, etc.) ──
    async def on_session_end(self, session_id: str, context: dict) -> None:
        """Called at the end of a session. Fire-and-forget."""
        pass
