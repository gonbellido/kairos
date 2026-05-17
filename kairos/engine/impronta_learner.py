from datetime import datetime, timezone
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
import logging

from kairos.core.impronta import Impronta
from kairos.memory.stores.case_store import CaseStore
from kairos.engine.profile_engine import ProfileEngine

logger = logging.getLogger(__name__)


class ImprontaLearner:
    """Adjusts impronta variables based on feedback outcomes."""

    def __init__(self, case_store: CaseStore, profile_engine: ProfileEngine):
        self._store = case_store
        self._profiles = profile_engine

    async def adjust(
        self,
        profile_id: str,
        window: int = 20,
        min_samples: int = 3,
    ) -> dict[str, float]:
        raw = await self._store.semantic_search(
            query="",
            profile_id=profile_id,
            top_k=window,
        )
        if len(raw) < min_samples:
            return {}

        # Compute success rate per impronta dimension
        deltas: dict[str, float] = {}
        for sc in raw:
            case = sc.case
            impronta = case.impronta_applied
            if not impronta or case.outcome is None:
                continue

            dims = ["directividad", "emocionalidad", "analiticidad", "riesgo",
                    "formalidad", "proactividad", "estructura", "personalizacion"]

            for dim in dims:
                value = getattr(impronta, dim, 0.5)
                weight = case.outcome - 0.5  # positive outcome = positive reinforcement
                delta = value * weight * 0.05  # gentle adjustment
                if dim not in deltas:
                    deltas[dim] = 0.0
                deltas[dim] += delta

        # Average
        count = max(len(raw), 1)
        adjustments = {k: round(v / count, 3) for k, v in deltas.items()}

        logger.info("Impronta adjustments for %s: %s", profile_id, adjustments)
        return adjustments

    async def apply_adjustments(
        self,
        profile_id: str,
        adjustments: dict[str, float],
    ) -> Impronta | None:
        if not adjustments:
            return None
        try:
            profile = await self._profiles.get_profile(profile_id)
            current = profile.default_impronta
            overrides = {}
            for dim, delta in adjustments.items():
                current_val = getattr(current, dim, 0.5)
                new_val = max(0.0, min(1.0, current_val + delta))
                overrides[dim] = round(new_val, 2)

            adjusted = current.update(overrides)
            logger.info("Applied impronta adjustments: %s", overrides)
            return adjusted
        except Exception as e:
            logger.warning("Failed to apply impronta adjustments: %s", e)
            return None
