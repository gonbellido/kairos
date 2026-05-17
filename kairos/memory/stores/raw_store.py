from datetime import datetime, timedelta, timezone
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from kairos.core.memory import RawMemory
from kairos.memory.embeddings import EmbeddingProvider

COLLECTION = "raw_memories"


class RawStore:
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

    async def store(self, raw: RawMemory) -> str:
        if not raw.id:
            raw.id = uuid4().hex
        content = (raw.content or "").strip()
        if not content:
            vector = [0.0] * self._embeddings.dimensions
        else:
            vector = await self._embeddings.embed(content[:2000])
        self._client.upsert(
            collection_name=COLLECTION,
            points=[qdrant_models.PointStruct(id=raw.id, vector=vector, payload=raw.model_dump(mode="json"))],
        )
        return raw.id

    async def search(
        self, query: str, profile_id: str, client_id: str = "", coach_id: str = "", top_k: int = 5
    ) -> list[RawMemory]:
        query = (query or "").strip()
        must = [qdrant_models.FieldCondition(key="profile_id", match=qdrant_models.MatchValue(value=profile_id))]
        if client_id:
            must.append(qdrant_models.FieldCondition(key="client_id", match=qdrant_models.MatchValue(value=client_id)))
        if coach_id:
            must.append(qdrant_models.FieldCondition(key="coach_id", match=qdrant_models.MatchValue(value=coach_id)))

        if not query:
            # Fallback to scroll if no query text (regression fix)
            results, _ = self._client.scroll(
                collection_name=COLLECTION,
                scroll_filter=qdrant_models.Filter(must=must),
                limit=top_k,
                with_payload=True,
                with_vectors=False,
            )
            return [RawMemory(**p.payload) for p in results]

        vector = await self._embeddings.embed(query[:2000])
        results = self._client.query_points(
            collection_name=COLLECTION,
            query=vector,
            query_filter=qdrant_models.Filter(must=must),
            limit=top_k,
            with_payload=True,
        )
        return [RawMemory(**p.payload) for p in results.points]

    async def search_relevant(
        self, query_text: str, profile_id: str, client_id: str = "", coach_id: str = "", top_k: int = 5
    ) -> list[dict]:
        """Búsqueda semántica que retorna payloads con score. Para coach assistant RAG."""
        query_text = (query_text or "").strip()
        must = [qdrant_models.FieldCondition(key="profile_id", match=qdrant_models.MatchValue(value=profile_id))]
        if client_id:
            must.append(qdrant_models.FieldCondition(key="client_id", match=qdrant_models.MatchValue(value=client_id)))
        if coach_id:
            must.append(qdrant_models.FieldCondition(key="coach_id", match=qdrant_models.MatchValue(value=coach_id)))

        if not query_text:
            # Fallback to scroll if no query text
            results, _ = self._client.scroll(
                collection_name=COLLECTION,
                scroll_filter=qdrant_models.Filter(must=must),
                limit=top_k,
                with_payload=True,
                with_vectors=False,
            )
            items = []
            for p in results:
                item = dict(p.payload or {})
                item["_point_id"] = str(p.id) if p.id else ""
                item["_score"] = 1.0
                items.append(item)
            return items

        vector = await self._embeddings.embed(query_text[:2000])
        results = self._client.query_points(
            collection_name=COLLECTION,
            query=vector,
            query_filter=qdrant_models.Filter(must=must),
            limit=top_k,
            with_payload=True,
        )
        items = []
        for p in results.points:
            item = dict(p.payload or {})
            item["_point_id"] = str(p.id) if p.id else ""
            item["_score"] = p.score
            items.append(item)
        return items

    def list_by_filter(
        self, profile_id: str, client_id: str = "", coach_id: str = "", limit: int = 100
    ) -> list[dict]:
        """Lista memorias por filtro usando scroll (sin búsqueda vectorial)."""
        must = [qdrant_models.FieldCondition(key="profile_id", match=qdrant_models.MatchValue(value=profile_id))]
        if client_id:
            must.append(qdrant_models.FieldCondition(key="client_id", match=qdrant_models.MatchValue(value=client_id)))
        if coach_id:
            must.append(qdrant_models.FieldCondition(key="coach_id", match=qdrant_models.MatchValue(value=coach_id)))
        results, _ = self._client.scroll(
            collection_name=COLLECTION,
            scroll_filter=qdrant_models.Filter(must=must),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        items = []
        for p in results:
            item = dict(p.payload or {})
            item["_point_id"] = str(p.id) if p.id else ""
            items.append(item)
        return items

    def delete_by_point_id(self, point_id: str) -> bool:
        """Elimina una memoria por su Qdrant point ID. Retorna True si se eliminó."""
        try:
            result = self._client.delete(
                collection_name=COLLECTION,
                points_selector=qdrant_models.PointIdsList(points=[point_id]),
                wait=True,
            )
            return result.status == qdrant_models.UpdateStatus.COMPLETED
        except Exception:
            return False

    def purge_expired(self, ttl_days: int) -> int:
        """Elimina memorias raw más antiguas que ttl_days. N1 tiene bajo valor a largo plazo."""
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
