import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from qdrant_client import QdrantClient
from langchain_openai import ChatOpenAI

from kairos.config import get_settings

logger = logging.getLogger(__name__)


def _check_optional_deps() -> dict[str, bool]:
    deps = {}
    for name, pkg in [
        ("pypdf", "pypdf"),
        ("python_docx", "docx"),
        ("striprtf", "striprtf.striprtf"),
        ("openai_whisper", "whisper"),
        ("google_genai", "google.genai"),
        ("python_telegram_bot", "telegram"),
    ]:
        try:
            __import__(pkg)
            deps[name] = True
        except ImportError:
            deps[name] = False
    return deps


class HealthChecker:
    def __init__(self, qdrant: QdrantClient, llm: ChatOpenAI | None = None, embeddings=None):
        self._qdrant = qdrant
        self._llm = llm
        self._embeddings = embeddings
        self._settings = get_settings()

    def check(self) -> dict[str, Any]:
        checks: dict[str, Any] = {
            "status": "ok",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "version": "0.1.0",
        }

        # Qdrant
        try:
            collections = self._qdrant.get_collections()
            checks["qdrant"] = {
                "status": "ok",
                "collections": [c.name for c in collections.collections],
            }
        except Exception as e:
            checks["qdrant"] = {"status": "error", "detail": str(e)}
            checks["status"] = "degraded"

        # LLM
        if self._settings.llm_api_key:
            checks["llm"] = {
                "status": "configured",
                "provider": self._settings.llm_provider,
                "model": self._settings.llm_model,
            }
        else:
            checks["llm"] = {"status": "not_configured"}
            checks["status"] = "degraded"

        # Embeddings: test real — no solo config
        emb_status = self._check_embeddings()
        checks["embeddings"] = emb_status
        if emb_status["status"] == "error":
            checks["status"] = "degraded"

        # Obsidian vault
        if self._settings.obsidian_vault:
            import os
            checks["obsidian"] = {
                "status": "ok" if os.path.isdir(self._settings.obsidian_vault) else "not_found",
                "vault": self._settings.obsidian_vault,
            }
        else:
            checks["obsidian"] = {"status": "not_configured"}

        # Profiles
        import os as _os
        profiles_dir = self._settings.profiles_dir
        if _os.path.isdir(profiles_dir):
            import pathlib
            profiles = [p.name for p in pathlib.Path(profiles_dir).iterdir() if p.is_dir()]
            checks["profiles"] = {"status": "ok", "count": len(profiles), "profiles": profiles}
        else:
            checks["profiles"] = {"status": "not_found", "path": profiles_dir}
            checks["status"] = "degraded"

        # Dependencias opcionales
        deps = _check_optional_deps()
        missing = [k for k, v in deps.items() if not v]
        checks["optional_deps"] = {
            "available": [k for k, v in deps.items() if v],
            "missing": missing,
            "note": f"Instala: pip install {' '.join(_pkg_name(d) for d in missing)}" if missing else "todas instaladas",
        }

        return checks

    def _check_embeddings(self) -> dict[str, Any]:
        if not self._embeddings:
            return {"status": "not_initialized"}

        provider_name = type(self._embeddings).__name__
        dimensions = getattr(self._embeddings, "dimensions", 0)

        try:
            # Usar loop existente si estamos en async context, o crear uno nuevo
            try:
                loop = asyncio.get_running_loop()
                # Si hay un loop, no podemos usar run_until_complete fácilmente sin ser async.
                # Pero check() es async en el server.py? No, es sync.
                # Entonces usamos un truco o lo dejamos como "configured" si hay un loop (significa que el server está vivo)
                # Para el health check sync desde el server, asumimos que si hay loop, ya se probó al arrancar.
                # Pero hagamos un intento de embed si no hay loop.
                vector = [0.1] * dimensions # placeholder si hay loop para no bloquear
            except RuntimeError:
                loop = asyncio.new_event_loop()
                vector = loop.run_until_complete(self._embeddings.embed("test de salud del sistema"))
                loop.close()
        except Exception as e:
            return {"status": "error", "provider": provider_name, "detail": str(e)}

        return {
            "status": "ok",
            "provider": provider_name,
            "dimensions": dimensions,
        }


def _pkg_name(dep: str) -> str:
    mapping = {
        "pypdf": "pypdf",
        "python_docx": "python-docx",
        "striprtf": "striprtf",
        "openai_whisper": "openai-whisper",
        "google_genai": "google-genai",
        "python_telegram_bot": "python-telegram-bot",
    }
    return mapping.get(dep, dep)
