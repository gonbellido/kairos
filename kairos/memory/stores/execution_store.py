from datetime import datetime, timedelta, timezone
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from kairos.core.memory import ExecutionMemory
from kairos.memory.embeddings import EmbeddingProvider

COLLECTION = "executions"


class ExecutionStore:
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

    async def store(self, exec_mem: ExecutionMemory) -> str:
        if not exec_mem.id:
            exec_mem.id = uuid4().hex
        vector = await self._embeddings.embed(exec_mem.input_text)
        self._client.upsert(
            collection_name=COLLECTION,
            points=[qdrant_models.PointStruct(id=exec_mem.id, vector=vector, payload=exec_mem.model_dump(mode="json"))],
        )
        return exec_mem.id

    async def search(self, query: str, profile_id: str, top_k: int = 5) -> list[ExecutionMemory]:
        vector = await self._embeddings.embed(query)
        results = self._client.query_points(
            collection_name=COLLECTION, query=vector,
            query_filter=qdrant_models.Filter(
                must=[qdrant_models.FieldCondition(key="profile_id", match=qdrant_models.MatchValue(value=profile_id))]
            ),
            limit=top_k, with_payload=True,
        )
        return [ExecutionMemory(**p.payload) for p in results.points]

    def purge_expired(self, ttl_days: int) -> int:
        """Elimina ejecuciones más antiguas que ttl_days. N4 es auditoría operativa de corto plazo."""
        cutoff_iso = (datetime.now(tz=timezone.utc) - timedelta(days=ttl_days)).isoformat()
        deleted = 0
        offset = None
        while True:
            results, next_offset = self._client.scroll(
                collection_name=COLLECTION,
                limit=100,
                with_payload=["created_at"],
                with_vectors=False,
                offset=offset,
            )
            ids_to_delete = [
                p.id for p in results
                if str(p.payload.get("created_at", "9999")) < cutoff_iso
            ]
            if ids_to_delete:
                self._client.delete(
                    collection_name=COLLECTION,
                    points_selector=qdrant_models.PointIdsList(points=ids_to_delete),
                )
                deleted += len(ids_to_delete)
            if next_offset is None:
                break
            offset = next_offset
        return deleted
