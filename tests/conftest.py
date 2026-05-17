import pytest
from qdrant_client import QdrantClient

from kairos.memory.stores import RawStore, CaseStore, PatternStore, ExecutionStore, KnowledgeStore
from kairos.memory.embeddings import EmbeddingProvider
from kairos.memory.scoring import ScoringEngine
from kairos.engine.profile_engine import ProfileEngine
from kairos.engine.prompt_engine import PromptEngine
from kairos.engine.state_classifier import StateClassifier


class FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dim: int = 128):
        self._dim = dim
    async def embed(self, text: str) -> list[float]:
        return [0.01] * self._dim
    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [[0.01] * self._dim for _ in texts]
    @property
    def dimensions(self) -> int:
        return self._dim


@pytest.fixture
def fake_embeddings() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def qdrant() -> QdrantClient:
    return QdrantClient(location=":memory:")


@pytest.fixture
def raw_store(qdrant, fake_embeddings) -> RawStore:
    s = RawStore(qdrant, fake_embeddings)
    s.ensure_collection(128)
    return s


@pytest.fixture
def case_store(qdrant, fake_embeddings) -> CaseStore:
    s = CaseStore(qdrant, fake_embeddings)
    s.ensure_collection(128)
    return s


@pytest.fixture
def pattern_store(qdrant, fake_embeddings) -> PatternStore:
    s = PatternStore(qdrant, fake_embeddings)
    s.ensure_collection(128)
    return s


@pytest.fixture
def execution_store(qdrant, fake_embeddings) -> ExecutionStore:
    s = ExecutionStore(qdrant, fake_embeddings)
    s.ensure_collection(128)
    return s


@pytest.fixture
def knowledge_store(qdrant, fake_embeddings) -> KnowledgeStore:
    s = KnowledgeStore(qdrant, fake_embeddings)
    s.ensure_collection(128)
    return s


@pytest.fixture
def scoring_engine() -> ScoringEngine:
    return ScoringEngine()


@pytest.fixture
def profile_engine() -> ProfileEngine:
    return ProfileEngine(profiles_dir="./profiles")


@pytest.fixture
def prompt_engine() -> PromptEngine:
    return PromptEngine()


@pytest.fixture
def classifier() -> StateClassifier:
    return StateClassifier()
