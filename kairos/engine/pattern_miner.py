import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

_utcnow = lambda: datetime.now(tz=timezone.utc)
from kairos.memory.stores.case_store import CaseStore
from kairos.memory.stores.pattern_store import PatternStore
from kairos.core.memory import PatternMemory

logger = logging.getLogger(__name__)


class PatternMiner:
    def __init__(self, case_store: CaseStore, pattern_store: PatternStore):
        self._cases = case_store
        self._patterns = pattern_store

    async def mine(self, profile_id: str, min_cases: int = 5) -> list[dict]:
        # Retrieve all cases for this profile via broad search
        import numpy as np

        raw = await self._cases.semantic_search(
            query=".", profile_id=profile_id, top_k=100,
        )
        if len(raw) < min_cases:
            logger.info("Only %d cases for %s, need %d", len(raw), profile_id, min_cases)
            return []

        embeddings = np.array([
            sc.semantic_score for sc in raw
        ])
        cases = [sc.case for sc in raw]

        if len(embeddings) < 3:
            return []

        # Simple cluster: split by outcome
        high = [c for c in cases if c.case.outcome and c.case.outcome > 0.5]
        low = [c for c in cases if c.case.outcome and c.case.outcome < 0.3]
        medium = [c for c in cases if c.case.outcome and 0.3 <= c.case.outcome <= 0.5]

        patterns = []
        for bucket, label, min_size in [
            (high, "success", 2), (low, "risk", 2), (medium, "neutral", 3),
        ]:
            if len(bucket) >= min_size:
                patterns.append(await self._build_pattern(profile_id, label, bucket))

        for p in patterns:
            await self._patterns.store(p)

        logger.info("Mined %d patterns for profile %s", len(patterns), profile_id)
        return [p.model_dump(mode="json") for p in patterns]

    async def _build_pattern(
        self, profile_id: str, pattern_type: str, cases: list,
    ) -> PatternMemory:
        def _outcome(c):
            if hasattr(c, 'case'):
                return getattr(c.case, 'outcome', None)
            return getattr(c, 'outcome', None)

        avg_outcome = sum(_outcome(c) or 0.5 for c in cases) / len(cases)
        categories = {}
        for c in cases:
            cat = c.case.metadata.category if hasattr(c, 'case') else c.metadata.category
            categories[cat] = categories.get(cat, 0) + 1
        top_cat = max(categories, key=categories.get) if categories else "general"

        return PatternMemory(
            id=uuid4().hex,
            profile_id=profile_id,
            pattern_type=pattern_type,
            title=f"Patrón {pattern_type}: {top_cat} (n={len(cases)})",
            description=(
                f"{len(cases)} casos con outcome promedio {avg_outcome:.2f}. "
                f"Categoría dominante: {top_cat}."
            ),
            statistical_signal=abs(avg_outcome - 0.5) * 2,
            frequency=len(cases),
            impact_score=avg_outcome,
            supporting_case_ids=[c.id for c in cases[:10]],
            metadata={
                "avg_outcome": round(avg_outcome, 3),
                "top_category": top_cat,
                "pattern_type": pattern_type,
            },
        )
