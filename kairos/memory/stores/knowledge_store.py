import hashlib
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from kairos.memory.embeddings import EmbeddingProvider

COLLECTION = "knowledge"


class KnowledgeStore:
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

    async def store_document(self, doc_id: str, content: str, metadata: dict | None = None) -> str:
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Deduplicación B5: evitar indexar el mismo documento dos veces
        existing, _ = self._client.scroll(
            collection_name=COLLECTION,
            scroll_filter=qdrant_models.Filter(
                must=[qdrant_models.FieldCondition(
                    key="content_hash", match=qdrant_models.MatchValue(value=content_hash),
                )]
            ),
            limit=1,
            with_payload=["id"],
            with_vectors=False,
        )
        if existing:
            return existing[0].payload.get("id", doc_id)

        vector = await self._embeddings.embed(content[:2000])
        self._client.upsert(
            collection_name=COLLECTION,
            points=[qdrant_models.PointStruct(
                id=doc_id, vector=vector,
                payload={
                    "id": doc_id,
                    "content": content,
                    "metadata": metadata or {},
                    "content_hash": content_hash,
                },
            )],
        )
        return doc_id

    async def search(self, query: str, top_k: int = 5, profile_id: str | None = None) -> list[dict]:
        query = (query or "").strip()
        qfilter = None
        if profile_id:
            qfilter = qdrant_models.Filter(
                must=[qdrant_models.FieldCondition(key="metadata.profile_id", match=qdrant_models.MatchValue(value=profile_id))]
            )

        if not query:
            results, _ = self._client.scroll(
                collection_name=COLLECTION,
                scroll_filter=qfilter,
                limit=top_k,
                with_payload=True,
                with_vectors=False,
            )
            return [{"id": p.payload["id"], "content": p.payload["content"],
                     "metadata": p.payload.get("metadata", {}), "score": 1.0} for p in results]

        vector = await self._embeddings.embed(query)
        results = self._client.query_points(
            collection_name=COLLECTION, query=vector,
            query_filter=qfilter, limit=top_k, with_payload=True,
        )
        return [{"id": p.payload["id"], "content": p.payload["content"],
                 "metadata": p.payload.get("metadata", {}), "score": p.score} for p in results.points]
