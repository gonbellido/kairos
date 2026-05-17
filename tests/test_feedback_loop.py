import pytest
from kairos.engine.feedback_processor import FeedbackProcessor
from kairos.engine.pattern_miner import PatternMiner
from kairos.memory.scoring import ScoringEngine
from kairos.core.memory import CaseMemory, CaseMetadata


@pytest.mark.asyncio
async def test_feedback_ingest_updates_metadata(case_store):
    engine = ScoringEngine()
    proc = FeedbackProcessor(case_store, engine)

    case = CaseMemory(profile_id="t", context="test feedback", intervention="resp")
    cid = await case_store.store(case)
    assert case_store.get(cid).metadata.feedback_score is None

    result = await proc.ingest_feedback(cid, 0.8)
    assert result["case_id"] == cid
    assert result["new_score"] == 0.8
    assert case_store.get(cid).metadata.feedback_score == 0.8


@pytest.mark.asyncio
async def test_feedback_invalid_score(case_store):
    engine = ScoringEngine()
    proc = FeedbackProcessor(case_store, engine)

    with pytest.raises(ValueError, match="Score must be between"):
        await proc.ingest_feedback("fake", 999)


@pytest.mark.asyncio
async def test_feedback_nonexistent_case(case_store):
    engine = ScoringEngine()
    proc = FeedbackProcessor(case_store, engine)

    with pytest.raises(ValueError, match="not found"):
        await proc.ingest_feedback("noexiste", 0.5)


@pytest.mark.asyncio
async def test_feedback_re_scores_similar(case_store):
    engine = ScoringEngine()
    proc = FeedbackProcessor(case_store, engine)

    c1 = await case_store.store(CaseMemory(profile_id="t", context="problema X", intervention="r1"))
    c2 = await case_store.store(CaseMemory(profile_id="t", context="problema X variante", intervention="r2"))

    result = await proc.ingest_feedback(c1, 0.9, comment="Excelente")
    assert result["re_scored_count"] >= 1


@pytest.mark.asyncio
async def test_pattern_miner_creates_patterns(case_store, pattern_store):
    miner = PatternMiner(case_store, pattern_store)

    for i in range(6):
        await case_store.store(CaseMemory(
            profile_id="t", context=f"caso {i}", intervention="r",
            outcome=0.8, metadata=CaseMetadata(category="ventas"),
        ))

    patterns = await miner.mine("t", min_cases=3)
    assert len(patterns) >= 1
    assert patterns[0]["pattern_type"] == "success"
    assert patterns[0]["statistical_signal"] > 0


@pytest.mark.asyncio
async def test_pattern_miner_insufficient_cases(case_store, pattern_store):
    miner = PatternMiner(case_store, pattern_store)
    patterns = await miner.mine("t", min_cases=10)
    assert patterns == []


@pytest.mark.asyncio
async def test_feedback_with_comment_adds_tag(case_store):
    engine = ScoringEngine()
    proc = FeedbackProcessor(case_store, engine)

    case = CaseMemory(profile_id="t", context="x", intervention="y")
    cid = await case_store.store(case)
    await proc.ingest_feedback(cid, -0.5, comment="Muy directivo")

    updated = case_store.get(cid)
    tags = updated.metadata.tags
    assert any("Muy directivo" in t for t in tags)
