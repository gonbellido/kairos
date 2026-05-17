import logging
from datetime import datetime, timezone
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
from kairos.memory.stores.case_store import CaseStore
from kairos.memory.scoring import ScoringEngine, ScoringWeights
from kairos.core.memory import CaseMemory, ScoredCase
from kairos.core.scoring_context import ScoringContext

logger = logging.getLogger(__name__)


class FeedbackProcessor:
    def __init__(self, case_store: CaseStore, scoring_engine: ScoringEngine):
        self._store = case_store
        self._scoring = scoring_engine

    async def ingest_feedback(
        self,
        case_id: str,
        score: float,
        comment: str | None = None,
    ) -> dict[str, Any]:
        if not -1.0 <= score <= 1.0:
            raise ValueError(f"Score must be between -1 and 1, got {score}")

        case = self._store.get(case_id)
        if not case:
            raise ValueError(f"Case {case_id} not found")

        old_feedback = case.metadata.feedback_score
        case.metadata.feedback_score = score
        if comment:
            case.metadata.tags.append(f"feedback:{comment[:50]}")

        self._store.update_metadata(case_id, case.model_dump(mode="json"))

        # Re-score similar cases
        affected = await self._re_score_similar(case)

        return {
            "case_id": case_id,
            "old_score": old_feedback,
            "new_score": score,
            "re_scored_count": affected,
        }

    async def _re_score_similar(self, reference: CaseMemory) -> int:
        similar = await self._store.semantic_search(
            query=reference.context,
            profile_id=reference.profile_id,
            top_k=20,
        )
        ctx = ScoringContext(profile_id=reference.profile_id)
        ranked = await self._scoring.score(similar, ctx)

        count = 0
        for r in ranked:
            self._store.update_metadata(
                r.case.id,
                {"composite_score_cache": r.composite_score},
            )
            count += 1

        logger.info("Re-scored %d cases similar to %s", count, reference.id)
        return count
