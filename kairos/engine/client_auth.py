"""Client authentication via unique access token."""

import logging
from uuid import uuid4

from kairos.core.client import ClientProfile

logger = logging.getLogger(__name__)


class ClientAuth:
    """Authenticates clients by their unique access token (no email/password)."""

    def __init__(self, client_store):
        self._store = client_store

    async def get_client_by_token(self, token: str) -> ClientProfile | None:
        """Find a client by their access token stored in metadata."""
        try:
            from qdrant_client.http import models as qm
            results = self._store._client.query_points(
                collection_name="client_profiles",
                query=[0.0] * self._store._embeddings.dimensions,
                query_filter=qm.Filter(must=[
                    qm.FieldCondition(
                        key="metadata.access_token",
                        match=qm.MatchValue(value=token),
                    ),
                ]),
                limit=1, with_payload=True,
            )
            if results.points:
                return ClientProfile(**results.points[0].payload)
        except Exception as e:
            logger.warning("Client auth failed: %s", e)
        return None

    async def get_client_by_id(self, client_id: str) -> ClientProfile | None:
        return self._store.get_profile(client_id)

    async def generate_token(self, client_id: str) -> str:
        """Generate and store a unique access token for a client."""
        token = uuid4().hex[:12]
        profile = self._store.get_profile(client_id)
        if profile:
            profile.metadata["access_token"] = token
            await self._store.upsert_profile(profile)
            return token
        return ""
