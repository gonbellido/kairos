import logging
import os

from kairos.memory.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)

try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    _GOOGLE_AVAILABLE = True
except ImportError:
    _GOOGLE_AVAILABLE = False


DIMENSIONS_MAP = {
    "models/embedding-001": 768,
    "models/gemini-embedding-001": 768,
    "models/gemini-embedding-2": 3072,
    "models/gemini-embedding-2-preview": 3072,
}


class GoogleEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        import os as _os
        self._model_name = model or _os.environ.get("EMBEDDING_MODEL", "models/gemini-embedding-2")
        self._api_key = api_key or _os.environ.get("GOOGLE_API_KEY", "")
        self._client = None
        if _GOOGLE_AVAILABLE and self._api_key:
            self._client = GoogleGenerativeAIEmbeddings(
                model=self._model_name,
                google_api_key=self._api_key,
            )
            logger.info("Google embeddings ready: %s (dims=%d)", self._model_name, self.dimensions)
        else:
            logger.warning("Google embeddings not available (install langchain-google-genai, set GOOGLE_API_KEY)")

    async def embed(self, text: str) -> list[float]:
        if not self._client:
            return [0.0] * self.dimensions
        return await self._client.aembed_query(text)

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not self._client:
            return [[0.0] * self.dimensions for _ in texts]
        return await self._client.aembed_documents(texts)

    @property
    def dimensions(self) -> int:
        return DIMENSIONS_MAP.get(self._model_name, 768)
