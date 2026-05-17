import asyncio
import logging
import numpy as np

from kairos.memory.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False
    logger.warning("sentence-transformers not installed. Install: pip install sentence-transformers")


class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None
        self._dim = 384

    def _get_model(self):
        if self._model is None and _ST_AVAILABLE:
            logger.info("Loading embedding model: %s", self._model_name)
            self._model = SentenceTransformer(self._model_name)
            self._dim = self._model.get_sentence_embedding_dimension()
        return self._model

    async def embed(self, text: str) -> list[float]:
        model = self._get_model()
        if model is None:
            return [0.0] * self._dim
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: model.encode(text[:2000]))
        return result.tolist()

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        if model is None:
            return [[0.0] * self._dim for _ in texts]
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None, lambda: model.encode([t[:2000] for t in texts])
        )
        return [r.tolist() for r in results]

    @property
    def dimensions(self) -> int:
        return self._dim
