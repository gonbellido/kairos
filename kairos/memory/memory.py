"""Etapa 7: Memory between sessions — Qdrant raw_memories.

- get_recent(): scroll by session_id, no embedding
- get_across_sessions(): semantic search across all sessions for a client
- append_raw(): store message without embedding (embedding computed later on search)
"""

import logging
from uuid import uuid4
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

VECTOR_DIM = 3072  # Gemini embedding-2


async def get_recent(session_id: str, limit: int = 5) -> list[dict]:
    """Last N messages of the current session. No embedding — scroll with filter."""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue

        qdrant = _get_qdrant()
        results, _ = await qdrant.scroll(
            collection_name="raw_memories",
            scroll_filter=Filter(must=[
                FieldCondition(key="session_id", match=MatchValue(value=session_id))
            ]),
            limit=limit,
            with_payload=True,
        )
        payloads = [r.payload for r in results if r.payload]
        payloads.sort(key=lambda p: p.get("timestamp", ""), reverse=True)
        return payloads
    except Exception as e:
        logger.warning("Memory get_recent failed: %s", e)
        return []


async def get_across_sessions(client_id: str, query: str, limit: int = 5) -> list[dict]:
    """Semantic search across all sessions for a client. 1 Gemini embed + 1 Qdrant query."""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue

        vector = await _embed(query)
        qdrant = _get_qdrant()
        results = await qdrant.search(
            collection_name="raw_memories",
            query_vector=vector,
            query_filter=Filter(must=[
                FieldCondition(key="client_id", match=MatchValue(value=client_id))
            ]),
            limit=limit,
        )
        return [r.payload for r in results if r.payload]
    except Exception as e:
        logger.warning("Memory get_across_sessions failed: %s", e)
        return []


async def append_raw(session_id: str, client_id: str, role: str, content: str) -> bool:
    """Store message in raw_memories WITHOUT embedding."""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import PointStruct

        qdrant = _get_qdrant()
        await qdrant.upsert(
            collection_name="raw_memories",
            points=[
                PointStruct(
                    id=str(uuid4()),
                    vector=[0.0] * VECTOR_DIM,
                    payload={
                        "session_id": session_id,
                        "client_id": client_id,
                        "role": role,
                        "content": content,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
            ],
        )
        return True
    except Exception as e:
        logger.warning("Memory append_raw failed: %s", e)
        return False


async def _embed(text: str) -> list[float]:
    """Embeds text with Gemini. Cached for repeated queries."""
    import os
    import hashlib

    key = hashlib.md5(text[:500].encode()).hexdigest()
    if key in _embed_cache:
        return _embed_cache[key]

    try:
        api_key = os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            return [0.0] * VECTOR_DIM

        import google.generativeai as genai
        genai.configure(api_key=api_key)
        result = await genai.embed_content_async(
            model="models/text-embedding-004",
            content=text[:2000],
        )
        vector = list(result.get("embedding", [0.0] * VECTOR_DIM))
        _embed_cache[key] = vector
        if len(_embed_cache) > 500:
            _embed_cache.pop(next(iter(_embed_cache)))
        return vector
    except Exception:
        return [0.0] * VECTOR_DIM


_embed_cache: dict[str, list[float]] = {}


def _get_qdrant():
    import os
    from qdrant_client import QdrantClient
    host = os.getenv("QDRANT_HOST", "qdrant")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    return QdrantClient(host=host, port=port)
