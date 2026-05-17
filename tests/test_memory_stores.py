import pytest
from kairos.core.memory import RawMemory, PatternMemory, ExecutionMemory


@pytest.mark.asyncio
async def test_raw_store(raw_store):
    r = RawMemory(profile_id="t", content="raw transcript", source_type="audio")
    rid = await raw_store.store(r)
    results = await raw_store.search("transcript", "t")
    assert len(results) == 1
    assert results[0].id == rid


@pytest.mark.asyncio
async def test_pattern_store(pattern_store):
    p = PatternMemory(profile_id="t", pattern_type="success", title="Test Pattern",
                       description="A test", statistical_signal=0.8, frequency=5)
    pid = await pattern_store.store(p)
    results = await pattern_store.search("test", "t")
    assert len(results) == 1
    assert results[0].id == pid
    assert results[0].statistical_signal == 0.8


@pytest.mark.asyncio
async def test_execution_store(execution_store):
    e = ExecutionMemory(session_id="s1", profile_id="t", input_text="hi", output_text="hello")
    eid = await execution_store.store(e)
    results = await execution_store.search("hi", "t")
    assert len(results) == 1
    assert results[0].id == eid


@pytest.mark.asyncio
async def test_knowledge_store(knowledge_store):
    from uuid import uuid4
    doc_id = uuid4().hex
    await knowledge_store.store_document(doc_id, "Investment strategies for 2025", {"profile_id": "financiero"})
    results = await knowledge_store.search("investment", profile_id="financiero")
    assert len(results) == 1
    assert "Investment strategies" in results[0]["content"]
