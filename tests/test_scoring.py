import pytest
from datetime import datetime, timezone, timedelta
from kairos.core.memory import CaseMemory, CaseMetadata, ScoredCase
from kairos.memory.scoring import ScoringEngine, RecencyScorer, OutcomeScorer


@pytest.mark.asyncio
async def test_ranking(scoring_engine):
    old = ScoredCase(case=CaseMemory(profile_id="t", context="old", intervention="r",
                                     metadata=CaseMetadata(outcome=-0.5, feedback_score=-0.3),
                                     created_at=datetime.now(tz=timezone.utc) - timedelta(days=100)), semantic_score=0.9)
    good = ScoredCase(case=CaseMemory(profile_id="t", context="good", intervention="r",
                                      metadata=CaseMetadata(outcome=0.9, feedback_score=0.8),
                                      created_at=datetime.now(tz=timezone.utc)), semantic_score=0.7)
    ranked = await scoring_engine.score([old, good])
    assert ranked[0].composite_score > ranked[1].composite_score


@pytest.mark.asyncio
async def test_recency_scorer():
    s = RecencyScorer(decay=0.05)
    old = ScoredCase(case=CaseMemory(profile_id="t", context="x", intervention="y",
                                     created_at=datetime.now(tz=timezone.utc) - timedelta(days=100)))
    new = ScoredCase(case=CaseMemory(profile_id="t", context="x", intervention="y",
                                     created_at=datetime.now(tz=timezone.utc)))
    assert await s.score(new, {}) > await s.score(old, {})


@pytest.mark.asyncio
async def test_outcome_scorer():
    s = OutcomeScorer()
    pos = ScoredCase(case=CaseMemory(profile_id="t", context="x", intervention="y",
                                     metadata=CaseMetadata(outcome=1.0, feedback_score=1.0)))
    neu = ScoredCase(case=CaseMemory(profile_id="t", context="x", intervention="y"))
    assert await s.score(pos, {}) > await s.score(neu, {})


@pytest.mark.asyncio
async def test_select_top(scoring_engine):
    cases = [ScoredCase(case=CaseMemory(profile_id="t", context=str(i), intervention="r"),
                        semantic_score=i / 10) for i in range(10)]
    ranked = await scoring_engine.score(cases)
    top = scoring_engine.select_top(ranked, 3)
    assert len(top) == 3
    assert top[0].composite_score >= top[1].composite_score >= top[2].composite_score
