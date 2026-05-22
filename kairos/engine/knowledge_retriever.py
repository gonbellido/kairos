"""Enhanced knowledge retriever with cross-document reranking and metadata scoring."""

from kairos.memory.stores.knowledge_store import KnowledgeStore
from kairos.engine.chunker import rerank_by_document


class KnowledgeRetriever:
    def __init__(self, store: KnowledgeStore, min_score: float = 0.3):
        self._store = store
        self._min_score = min_score

    async def retrieve(self, query: str, profile_id: str | None = None,
                       top_k: int = 5, rerank: bool = True) -> list[dict]:
        results = await self._store.search(query=query, top_k=top_k * 3, profile_id=profile_id)
        filtered = [r for r in results if r.get("_score", 0) >= self._min_score]
        if rerank and len(filtered) > 1:
            return rerank_by_document(filtered, top_k=top_k)
        return filtered[:top_k]

    async def retrieve_with_context(self, query: str, profile_id: str | None = None,
                                     top_k: int = 5) -> str:
        docs = await self.retrieve(query, profile_id, top_k)
        if not docs:
            return ""
        parts = []
        for d in docs:
            section = d.get("metadata", {}).get("section", "") or d.get("section", "")
            filename = d.get("metadata", {}).get("filename", "") or d.get("filename", "")
            header = f"[{filename}]" if filename else ""
            if section:
                header += f" / {section}"
            text = d.get("content", "") or d.get("text", "")
            parts.append(f"{header}\n{text[:500]}" if header else text[:500])
        return "\n---\n".join(parts)
