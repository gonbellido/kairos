from langchain_openai import OpenAIEmbeddings

from kairos.config import get_settings
from .provider import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self._model = model or settings.embedding_model
        kwargs = {
            "model": self._model,
            "api_key": api_key or settings.embedding_api_key,
        }
        if settings.embedding_base_url:
            kwargs["base_url"] = settings.embedding_base_url
        self._client = OpenAIEmbeddings(**kwargs)

    async def embed(self, text: str) -> list[float]:
        return await self._client.aembed_query(text)

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        return await self._client.aembed_documents(texts)

    @property
    def dimensions(self) -> int:
        return get_settings().embedding_dimensions
