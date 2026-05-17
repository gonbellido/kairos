from kairos.memory.stores.knowledge_store import KnowledgeStore


class KnowledgeRetriever:
    def __init__(self, store: KnowledgeStore):
        self._store = store

    async def retrieve(self, query: str, profile_id: str | None = None, top_k: int = 5) -> list[dict]:
        return await self._store.search(query=query, top_k=top_k, profile_id=profile_id)
