import asyncio
import logging
from functools import wraps
from typing import Any, Callable, TypeVar

from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def retry_qdrant(max_retries: int = 3, base_delay: float = 0.5):
    """Decorator for Qdrant operations with exponential backoff."""
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning("Qdrant retry %d/%d: %s. Waiting %.1fs",
                                       attempt + 1, max_retries, e, delay)
                        time = __import__("time")
                        time.sleep(delay)
            logger.error("Qdrant failed after %d retries: %s", max_retries, last_exc)
            raise last_exc
        return wrapper  # type: ignore
    return decorator


class GracefulDegrader:
    """Provides fallback values when external services fail."""

    @staticmethod
    def empty_case_search() -> list:
        return []

    @staticmethod
    def default_profile() -> dict:
        return {"id": "fallback", "name": "Fallback", "default_impronta": {}}

    @staticmethod
    def fallback_response(profile_id: str, message: str) -> str:
        return (
            f"Lo siento, estoy teniendo dificultades técnicas. "
            f"Por favor, intenta de nuevo en unos momentos."
        )
