from uuid import uuid4
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from kairos.core.memory import PatternMemory
from kairos.memory.embeddings import EmbeddingProvider

COLLECTION = "patterns"


class PatternStore:
    def __init__(self, client: QdrantClient, embeddings: EmbeddingProvider):
        self._client = client
        self._embeddings = embeddings

    def ensure_collection(self, vector_size: int | None = None) -> None:
        existing = {c.name for c in self._client.get_collections().collections}
        if COLLECTION in existing:
            return
        self._client.create_collection(
            collection_name=COLLECTION,
            vectors_config=qdrant_models.VectorParams(
                size=vector_size or self._embeddings.dimensions,
                distance=qdrant_models.Distance.COSINE,
            ),
        )

    async def store(self, pattern: PatternMemory) -> str:
        if not pattern.id:
            pattern.id = uuid4().hex
        pattern_text = f"{pattern.title}: {pattern.description}"
        if not pattern_text.strip():
            pattern_text = " "
        vector = await self._embeddings.embed(pattern_text)
        self._client.upsert(
            collection_name=COLLECTION,
            points=[qdrant_models.PointStruct(id=pattern.id, vector=vector, payload=pattern.model_dump(mode="json"))],
        )
        return pattern.id

    async def search(self, query: str, profile_id: str, top_k: int = 5) -> list[PatternMemory]:
        vector = await self._embeddings.embed(query)
        results = self._client.query_points(
            collection_name=COLLECTION, query=vector,
            query_filter=qdrant_models.Filter(
                must=[qdrant_models.FieldCondition(key="profile_id", match=qdrant_models.MatchValue(value=profile_id))]
            ),
            limit=top_k, with_payload=True,
        )
        return [PatternMemory(**p.payload) for p in results.points]
