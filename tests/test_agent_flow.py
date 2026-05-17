import pytest
from kairos.engine.state_classifier import StateClassifier
from kairos.engine.imprint_mapper import ImprintMapper
from kairos.engine.pattern_generator import PatternGenerator
from kairos.engine.confidence_calculator import ConfidenceCalculator
from kairos.memory.scoring import ScoringEngine
from kairos.core.memory import CaseMemory, ScoredCase
from kairos.core.scoring_context import ScoringContext as SC


@pytest.mark.asyncio
async def test_perception_node(classifier):
    from kairos.agents.nodes.perception import perception_node
    state = {"session_id": "s1", "profile_id": "coaching", "user_id": "u1",
             "message": "Estoy muy frustrado con mi trabajo", "context": {}, "next_agent": "perception"}
    result = await perception_node(state, classifier)
    assert "state_classification" in result
    assert result["state_classification"]["emocion"] == "negative"
    assert result["next_agent"] == "memory"  # Make sure old constant doesn't break
    assert result.get("next_agent") is not None


@pytest.mark.asyncio
async def test_retrieve_node(qdrant, fake_embeddings, case_store, knowledge_store):
    from kairos.agents.nodes.retrieve import retrieve_node
    from kairos.engine.knowledge_retriever import KnowledgeRetriever
    from kairos.memory.stores.raw_store import RawStore
    from kairos.memory.stores.pattern_store import PatternStore

    raw_store = RawStore(qdrant, fake_embeddings)
    raw_store.ensure_collection(128)
    pattern_store = PatternStore(qdrant, fake_embeddings)
    pattern_store.ensure_collection(128)
    await case_store.store(CaseMemory(profile_id="coaching", context="frustrado con trabajo", intervention="¿Qué te frustra?", outcome=0.8))

    retriever = KnowledgeRetriever(knowledge_store)
    state = {"session_id": "s1", "profile_id": "coaching", "user_id": "u1",
             "message": "Estoy frustrado", "context": {}, "next_agent": "perception"}
    result = await retrieve_node(state, raw_store, case_store, pattern_store, retriever)
    assert "retrieved_cases" in result
    assert result["next_agent"] == "score"


@pytest.mark.asyncio
async def test_score_node(case_store):
    from kairos.agents.nodes.score import score_node

    await case_store.store(CaseMemory(profile_id="t", context="test", intervention="resp"))
    engine = ScoringEngine()
    state = {
        "session_id": "s1", "profile_id": "t", "user_id": "u1",
        "message": "test", "context": {},
        "retrieved_cases": [CaseMemory(profile_id="t", context="prev", intervention="prev")],
        "next_agent": "retrieve",
    }
    result = await score_node(state, engine)
    assert "ranked_cases" in result
    assert result["next_agent"] == "aggregate"


@pytest.mark.asyncio
async def test_aggregate_node():
    from kairos.agents.nodes.aggregate import aggregate_node
    from kairos.core.impronta import Impronta

    state = {
        "session_id": "s1", "profile_id": "coaching", "user_id": "u1",
        "message": "test", "context": {},
        "impronta": Impronta(directividad=0.3, emocionalidad=0.8),
        "retrieved_cases": [
            CaseMemory(profile_id="coaching", context="a", intervention="b", outcome=0.9,
                       state_classification={"emocion": "positive"}),
            CaseMemory(profile_id="coaching", context="c", intervention="d", outcome=0.7,
                       state_classification={"emocion": "positive"}),
            CaseMemory(profile_id="coaching", context="e", intervention="f", outcome=0.2,
                       state_classification={"emocion": "negative"}),
        ],
        "next_agent": "score",
    }
    result = await aggregate_node(state, PatternGenerator(), ImprintMapper())
    assert "impronta_rules" in result
    assert "insights" in result
    assert "context_signature" in result
    assert len(result["impronta_rules"]) > 0
    assert result["next_agent"] == "worker"


def test_confidence_calculator():
    conf, details = ConfidenceCalculator.calculate(
        ranked_cases=[], evaluation_score=0.8,
        impronta_adherence=0.9, case_count=5,
    )
    assert 0 <= conf <= 1
    assert "score_avg" in details


def test_imprint_mapper():
    from kairos.core.impronta import Impronta
    mapper = ImprintMapper()
    impronta = Impronta(directividad=0.3, emocionalidad=0.8, analiticidad=0.9, riesgo=0.2)
    rules = mapper.map(impronta)
    assert len(rules) > 0
    assert any("preguntas" in r.lower() for r in rules)


@pytest.mark.asyncio
async def test_scoring_context():
    engine = ScoringEngine()
    ctx = SC(state={"emocion": "negative"})
    cases = [ScoredCase(
        case=CaseMemory(profile_id="t", context="x", intervention="y",
                        state_classification={"emocion": "negative"}),
        semantic_score=0.5,
    )]
    ranked = await engine.score(cases, ctx)
    assert len(ranked) == 1
    assert "contextual" in ranked[0].scoring_details
