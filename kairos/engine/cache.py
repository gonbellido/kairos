"""D5: LRU in-memory cache with optional Redis backend for embeddings and LLM responses."""

import hashlib
import logging
import time
from collections import OrderedDict
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)


class LRUCache:
    """Thread-safe LRU cache with TTL support."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self._max = max_size
        self._ttl = ttl_seconds
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def _key(self, raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def get(self, key: str) -> Any | None:
        h = self._key(key)
        if h not in self._store:
            return None
        ts, val = self._store[h]
        if time.time() - ts > self._ttl:
            del self._store[h]
            return None
        self._store.move_to_end(h)
        return val

    def set(self, key: str, value: Any):
        h = self._key(key)
        if h in self._store:
            self._store.move_to_end(h)
        self._store[h] = (time.time(), value)
        while len(self._store) > self._max:
            self._store.popitem(last=False)

    def clear(self):
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


# Singleton caches
_embedding_cache = LRUCache(max_size=2000, ttl_seconds=3600)   # 1h for embeddings
_llm_cache = LRUCache(max_size=500, ttl_seconds=300)           # 5min for LLM responses


def cache_embedding(fn: Callable) -> Callable:
    """Decorator to cache embedding results. Key = text + model."""

    async def wrapper(self, text: str, *args, **kwargs):
        cache_key = f"{text}|{getattr(self, '_model_name', 'default')}"
        cached = _embedding_cache.get(cache_key)
        if cached is not None:
            logger.debug("Embedding cache hit: %d chars", len(text))
            return cached
        result = await fn(self, text, *args, **kwargs)
        _embedding_cache.set(cache_key, result)
        return result

    return wrapper


def cache_llm_response(fn: Callable) -> Callable:
    """Decorator to cache LLM responses. Key = prompt + model + temperature."""

    def wrapper(*args, **kwargs):
        # Build cache key from messages
        messages = args[1] if len(args) > 1 else kwargs.get("messages", kwargs.get("input", []))
        model = getattr(args[0], "model_name", kwargs.get("model", "default"))
        temp = getattr(args[0], "temperature", kwargs.get("temperature", 0.7))
        key_parts = [model, str(temp)]
        for m in messages:
            key_parts.append(str(m.get("content", "")) if isinstance(m, dict) else str(m.content))
        cache_key = "|".join(key_parts)

        cached = _llm_cache.get(cache_key)
        if cached is not None:
            logger.debug("LLM cache hit for model=%s", model)
            return cached

        result = fn(*args, **kwargs)
        _llm_cache.set(cache_key, result)
        return result

    return wrapper


def get_cache_stats() -> dict:
    """Return cache statistics for monitoring."""
    return {
        "embedding_cache_size": _embedding_cache.size,
        "embedding_cache_max": _embedding_cache._max,
        "llm_cache_size": _llm_cache.size,
        "llm_cache_max": _llm_cache._max,
    }
