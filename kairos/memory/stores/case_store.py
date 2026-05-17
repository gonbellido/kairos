import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from kairos.core.memory import CaseMemory, ScoredCase
from kairos.memory.embeddings import EmbeddingProvider

COLLECTION = "cases"


class CaseStore:
    def __init__(self, client: QdrantClient, embeddings: EmbeddingProvider):
        self._client = client
        self._embeddings = embeddings

    def ensure_collection(self, vector_size: int | None = None) -> None:
        existing = {c.name for c in self._client.get_collections().collections}
        if COLLECTION in existing:
            return
        size = vector_size or self._embeddings.dimensions
        self._client.create_collection(
            collection_name=COLLECTION,
            vectors_config=qdrant_models.VectorParams(size=size, distance=qdrant_models.Distance.COSINE),
        )

    async def store(self, case: CaseMemory) -> str:
        content_hash = hashlib.sha256(case.context.encode()).hexdigest()

        # Deduplicación B5: si ya existe un caso con el mismo hash para este perfil, incrementar uso
        existing, _ = self._client.scroll(
            collection_name=COLLECTION,
            scroll_filter=qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(key="profile_id", match=qdrant_models.MatchValue(value=case.profile_id)),
                    qdrant_models.FieldCondition(key="metadata.content_hash", match=qdrant_models.MatchValue(value=content_hash)),
                ]
            ),
            limit=1,
            with_payload=["id"],
            with_vectors=False,
        )
        if existing:
            existing_id = existing[0].payload.get("id", "")
            if existing_id:
                self.increment_usage(existing_id)
                return existing_id

        if not case.id:
            case.id = uuid4().hex
        case.metadata.content_hash = content_hash
        ctx = (case.context or "").strip()
        vector = await self._embeddings.embed(ctx if ctx else " ") if ctx else [0.0] * self._embeddings.dimensions
        self._client.upsert(
            collection_name=COLLECTION,
            points=[qdrant_models.PointStruct(id=case.id, vector=vector, payload=case.model_dump(mode="json"))],
        )
        return case.id

    async def semantic_search(
        self, query: str, profile_id: str, client_id: str = "", filters: dict | None = None,
        top_k: int = 10, score_threshold: float = 0.0,
    ) -> list[ScoredCase]:
        query = (query or "").strip()
        if not query:
            vector = [0.0] * self._embeddings.dimensions
        else:
            vector = await self._embeddings.embed(query)
        qfilter = self._build_filter(profile_id, client_id, filters)
        results = self._client.query_points(
            collection_name=COLLECTION, query=vector,
            query_filter=qfilter, limit=top_k,
            score_threshold=score_threshold, with_payload=True,
        )
        return [ScoredCase(case=CaseMemory(**p.payload), semantic_score=p.score) for p in results.points]

    def get(self, case_id: str) -> CaseMemory | None:
        results = self._client.retrieve(collection_name=COLLECTION, ids=[case_id], with_payload=True)
        return CaseMemory(**results[0].payload) if results else None

    def update_metadata(self, case_id: str, metadata: dict) -> None:
        self._client.set_payload(collection_name=COLLECTION, payload=metadata, points=[case_id])

    def increment_usage(self, case_id: str) -> None:
        case = self.get(case_id)
        if case:
            new_count = case.metadata.usage_count + 1
            self._client.set_payload(
                collection_name=COLLECTION,
                payload={"metadata": {"usage_count": new_count}},
                points=[case_id],
            )

    def purge_expired(self, ttl_days: int) -> int:
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

    def _build_filter(self, profile_id: str, client_id: str = "", filters: dict | None = None) -> qdrant_models.Filter | None:
        must = [qdrant_models.FieldCondition(key="profile_id", match=qdrant_models.MatchValue(value=profile_id))]
        if client_id:
            must.append(qdrant_models.FieldCondition(key="client_id", match=qdrant_models.MatchValue(value=client_id)))
        if filters:
            for key, value in filters.items():
                if isinstance(value, list):
                    must.append(qdrant_models.FieldCondition(key=key, match=qdrant_models.MatchAny(any=value)))
                elif isinstance(value, dict):
                    must.append(qdrant_models.FieldCondition(key=key, range=qdrant_models.Range(**value)))
                else:
                    must.append(qdrant_models.FieldCondition(key=key, match=qdrant_models.MatchValue(value=value)))
        return qdrant_models.Filter(must=must) if must else None
