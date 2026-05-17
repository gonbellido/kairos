import pytest
from uuid import uuid4
from kairos.core.memory import RawMemory, CaseMemory, PatternMemory, ExecutionMemory

@pytest.mark.asyncio
async def test_raw_store_empty_query_fallback(raw_store, qdrant):
    # Store a memory
    r = RawMemory(profile_id="t", content="important content", source_type="text")
    await raw_store.store(r)

    # Search with empty query - should trigger fallback to scroll
    # and return the result despite no vector search
    results = await raw_store.search("", "t")
    assert len(results) == 1
    assert results[0].content == "important content"

@pytest.mark.asyncio
async def test_raw_store_relevant_empty_query_fallback(raw_store):
    r = RawMemory(profile_id="t", content="relevant content", source_type="text")
    await raw_store.store(r)

    results = await raw_store.search_relevant("", "t")
    assert len(results) == 1
    assert results[0]["content"] == "relevant content"
    assert results[0]["_score"] == 1.0

@pytest.mark.asyncio
async def test_execution_store_empty_query_fallback(execution_store):
    e = ExecutionMemory(session_id="s1", profile_id="t", input_text="hi", output_text="hello")
    await execution_store.store(e)
    results = await execution_store.search("", "t")
    assert len(results) == 1
    assert results[0].input_text == "hi"

@pytest.mark.asyncio
async def test_pattern_store_empty_query_fallback(pattern_store):
    p = PatternMemory(profile_id="t", pattern_type="success", title="P1", description="D1")
    await pattern_store.store(p)
    results = await pattern_store.search("", "t")
    assert len(results) == 1
    assert results[0].title == "P1"

@pytest.mark.asyncio
async def test_case_store_empty_query_fallback(case_store):
    c = CaseMemory(profile_id="t", context="ctx", intervention="res")
    await case_store.store(c)
    results = await case_store.semantic_search("", "t")
    assert len(results) == 1
    assert results[0].case.context == "ctx"

@pytest.mark.asyncio
async def test_knowledge_store_empty_query_fallback(knowledge_store):
    doc_id = uuid4().hex
    await knowledge_store.store_document(doc_id, "knowledge content", {"profile_id": "t"})
    results = await knowledge_store.search("", profile_id="t")
    assert len(results) == 1
    assert results[0]["content"] == "knowledge content"
