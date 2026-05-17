"""Multimodal embedding provider using google.genai native client.
Soporta texto, PDFs, imágenes, audio y video directamente.
"""
import asyncio
import logging
import os
from typing import Any

from kairos.memory.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False
    logger.warning("google-genai not installed. pip install google-genai")

DIMENSIONS_MAP = {
    "models/gemini-embedding-001": 768,
    "models/gemini-embedding-2": 3072,
    "models/gemini-embedding-2-preview": 3072,
}

MIME_MAP = {
    ".pdf": "application/pdf",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".mp4": "video/mp4",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".txt": "text/plain",
    ".md": "text/plain",
    ".csv": "text/plain",
    ".json": "text/plain",
    ".html": "text/html",
    ".rtf": "application/rtf",
}


class GoogleMultimodalEmbeddingProvider(EmbeddingProvider):
    """Provider que usa google.genai directamente.
    Embedding multimodal: texto, PDF, audio, imágenes, video.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._model_name = model or os.environ.get("EMBEDDING_MODEL", "models/gemini-embedding-2")
        self._api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self._client = None
        if _GENAI_AVAILABLE and self._api_key:
            self._client = genai.Client(api_key=self._api_key)
            logger.info("Gemini multimodal embedding ready: %s (%dd)", self._model_name, self.dimensions)
        else:
            logger.warning("Gemini not available (install google-genai, set GOOGLE_API_KEY)")

    async def embed(self, text_or_bytes: str | bytes, mime_type: str | None = None) -> list[float]:
        """Embed text, PDF, audio, image, etc. usando gemini-embedding-2 multimodal."""
        if not self._client:
            return [0.0] * self.dimensions

        if isinstance(text_or_bytes, bytes):
            part = types.Part.from_bytes(data=text_or_bytes, mime_type=mime_type or "application/octet-stream")
        else:
            part = types.Part.from_text(text=text_or_bytes)

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._client.models.embed_content(
                model=self._model_name,
                contents=[part],
            ),
        )
        if result and result.embeddings:
            return result.embeddings[0].values or [0.0] * self.dimensions
        return [0.0] * self.dimensions

    async def embed_many(self, items: list[str | bytes], mime_types: list[str] | None = None) -> list[list[float]]:
        if not self._client:
            return [[0.0] * self.dimensions for _ in items]

        parts = []
        for i, item in enumerate(items):
            if isinstance(item, bytes):
                mt = mime_types[i] if mime_types and i < len(mime_types) else "application/octet-stream"
                parts.append(types.Part.from_bytes(data=item, mime_type=mt))
            else:
                parts.append(types.Part.from_text(text=item))

        loop = asyncio.get_running_loop()
        results = []
        for part in parts:
            result = await loop.run_in_executor(
                None,
                lambda p=part: self._client.models.embed_content(
                    model=self._model_name, contents=[p],
                ),
            )
            if result and result.embeddings:
                results.append(result.embeddings[0].values or [0.0] * self.dimensions)
            else:
                results.append([0.0] * self.dimensions)
        return results

    @property
    def dimensions(self) -> int:
        return DIMENSIONS_MAP.get(self._model_name, 3072)
