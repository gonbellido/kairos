from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from kairos.core.client import ClientProfile, Alert
from kairos.memory.embeddings import EmbeddingProvider

COLLECTION_CLIENTS = "client_profiles"
COLLECTION_ALERTS = "alerts"


class ClientStore:
    def __init__(self, client: QdrantClient, embeddings: EmbeddingProvider):
        self._client = client
        self._embeddings = embeddings

    def ensure_collections(self, vector_size: int | None = None) -> None:
        existing = {c.name for c in self._client.get_collections().collections}
        size = vector_size or self._embeddings.dimensions
        for col in (COLLECTION_CLIENTS, COLLECTION_ALERTS):
            if col not in existing:
                self._client.create_collection(
                    collection_name=col,
                    vectors_config=qdrant_models.VectorParams(
                        size=size, distance=qdrant_models.Distance.COSINE,
                    ),
                )

    async def upsert_profile(self, profile: ClientProfile) -> str:
        if not profile.id:
            profile.id = uuid4().hex
        # Embed a descripción semántica del perfil para permitir ClientSimilarityScorer
        embed_text = (
            f"{profile.nombre} "
            f"{profile.estado_actual.emocional} "
            f"{profile.metadata.get('contexto', '')} "
            f"{' '.join(str(o.titulo) for o in profile.objetivos)}"
        )
        vector = await self._embeddings.embed(embed_text)
        self._client.upsert(
            collection_name=COLLECTION_CLIENTS,
            points=[qdrant_models.PointStruct(
                id=profile.id,
                vector=vector,
                payload=profile.model_dump(mode="json"),
            )],
        )
        return profile.id

    def get_profile(self, client_id: str) -> ClientProfile | None:
        # scroll es correcto para recuperación por filtro exacto sin vector search
        results, _ = self._client.scroll(
            collection_name=COLLECTION_CLIENTS,
            scroll_filter=qdrant_models.Filter(
                must=[qdrant_models.FieldCondition(
                    key="id", match=qdrant_models.MatchValue(value=client_id),
                )],
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        return ClientProfile(**results[0].payload) if results else None

    async def search_by_coach(self, coach_id: str) -> list[ClientProfile]:
        results, _ = self._client.scroll(
            collection_name=COLLECTION_CLIENTS,
            scroll_filter=qdrant_models.Filter(
                must=[qdrant_models.FieldCondition(
                    key="coach_id",
                    match=qdrant_models.MatchValue(value=coach_id),
                )],
            ),
            limit=100, with_payload=True, with_vectors=False,
        )
        return [ClientProfile(**p.payload) for p in results]

    async def list_all(self) -> list[ClientProfile]:
        results, _ = self._client.scroll(
            collection_name=COLLECTION_CLIENTS,
            limit=200, with_payload=True, with_vectors=False,
        )
        return [ClientProfile(**p.payload) for p in results]

    async def store_alert(self, alert: Alert) -> str:
        if not alert.id:
            alert.id = uuid4().hex
        self._client.upsert(
            collection_name=COLLECTION_ALERTS,
            points=[qdrant_models.PointStruct(
                id=alert.id,
                vector=[0.0] * self._embeddings.dimensions,
                payload=alert.model_dump(mode="json"),
            )],
        )
        return alert.id

    def delete_profile(self, client_id: str) -> bool:
        try:
            self._client.delete(
                collection_name=COLLECTION_CLIENTS,
                points_selector=qdrant_models.PointIdsList(points=[client_id]),
            )
            return True
        except Exception:
            return False

    def get_active_alerts(self, coach_id: str) -> list[Alert]:
        must = [
            qdrant_models.FieldCondition(
                key="activa", match=qdrant_models.MatchValue(value=True),
            ),
            qdrant_models.FieldCondition(
                key="coach_id", match=qdrant_models.MatchValue(value=coach_id),
            ),
        ]
        results, _ = self._client.scroll(
            collection_name=COLLECTION_ALERTS,
            scroll_filter=qdrant_models.Filter(must=must),
            limit=50,
            with_payload=True,
            with_vectors=False,
        )
        return [Alert(**p.payload) for p in results]
