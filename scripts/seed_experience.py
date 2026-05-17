#!/usr/bin/env python3
"""Seed KAIROS with initial experience data from historical conversations.
Usage: python scripts/seed_experience.py --input conversations.json

JSON format:
[
  {
    "profile_id": "coaching",
    "context": "cliente dijo X",
    "intervention": "coach respondió Y",
    "outcome": 0.8,
    "category": "consulta",
    "tags": ["carrera"],
    "source": "historical"
  }
]
"""
import asyncio
import json
import logging
from pathlib import Path

from qdrant_client import QdrantClient
from kairos.config import get_settings
from kairos.memory.stores import CaseStore, RawStore, PatternStore
from kairos.memory.embeddings import OpenAIEmbeddingProvider, GoogleEmbeddingProvider, LocalEmbeddingProvider
from kairos.core.memory import CaseMemory, CaseMetadata, RawMemory, PatternMemory
from kairos.engine.pattern_miner import PatternMiner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _resolve_embeddings():
    import os as _os
    google_key = _os.environ.get("GOOGLE_API_KEY") or get_settings().embedding_api_key
    if google_key:
        return GoogleEmbeddingProvider(api_key=google_key)
    if get_settings().embedding_api_key:
        return OpenAIEmbeddingProvider()
    return LocalEmbeddingProvider()


async def seed_from_json(json_path: str):
    settings = get_settings()
    qdrant = QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        check_compatibility=False,
    )
    emb = _resolve_embeddings()
    case_store = CaseStore(qdrant, emb)
    raw_store = RawStore(qdrant, emb)
    pattern_store = PatternStore(qdrant, emb)

    case_store.ensure_collection()
    raw_store.ensure_collection()
    pattern_store.ensure_collection()

    logger.info("Seeding %d records from %s (embeddings: %s)", len(records), json_path, type(emb).__name__)

    stats = {"cases": 0, "raw": 0, "patterns": 0}
    for rec in records:
        profile = rec.get("profile_id", "coaching")

        # N1: raw memory
        raw = RawMemory(
            profile_id=profile,
            content=f"{rec.get('context', '')} → {rec.get('intervention', '')}",
            source_type=rec.get("source", "historical"),
            metadata={"category": rec.get("category", "general")},
        )
        await raw_store.store(raw)
        stats["raw"] += 1

        # N2: structured case
        case = CaseMemory(
            profile_id=profile,
            context=rec.get("context", ""),
            intervention=rec.get("intervention", ""),
            outcome=rec.get("outcome"),
            metadata=CaseMetadata(
                category=rec.get("category", "general"),
                tags=rec.get("tags", []),
                source=rec.get("source", "historical"),
                outcome=rec.get("outcome"),
            ),
        )
        await case_store.store(case)
        stats["cases"] += 1

    # N3: mine patterns from seeded data
    miner = PatternMiner(case_store, pattern_store)
    for profile in set(r.get("profile_id", "coaching") for r in records):
        mined = await miner.mine(profile, min_cases=3)
        stats["patterns"] += len(mined)

    qdrant.close()
    logger.info("Seeding complete: %s", stats)
    return stats


async def seed_sample():
    """Seed with built-in sample conversations when no JSON file is provided."""
    samples = [
        {"profile_id": "coaching", "context": "No sé qué hacer con mi carrera, me siento estancado",
         "intervention": "¿Qué significa exactamente estancado para ti? ¿Es falta de movimiento o falta de dirección?",
         "outcome": 0.8, "category": "consulta", "tags": ["carrera", "proposito"], "source": "sample"},
        {"profile_id": "coaching", "context": "Mi equipo no rinde como esperaba",
         "intervention": "¿Cómo defines rendir? ¿Y cómo sabes que no está rindiendo? A veces lo que medimos no es lo que importa.",
         "outcome": 0.6, "category": "consulta", "tags": ["liderazgo"], "source": "sample"},
        {"profile_id": "coaching", "context": "Tengo miedo de tomar la decisión equivocada",
         "intervention": "El miedo no es un indicador de que estés equivocado, sino de que te importa. ¿Qué necesitarías saber para sentirte más seguro?",
         "outcome": 0.9, "category": "consulta", "tags": ["miedo", "decisiones"], "source": "sample"},
        {"profile_id": "coaching", "context": "Siento que no avanzo, estoy dando vueltas en círculos",
         "intervention": "A veces lo que parece un círculo es una espiral. ¿Qué has aprendido en esta vuelta que no sabías en la anterior?",
         "outcome": 0.7, "category": "seguimiento", "tags": ["estancamiento", "progreso"], "source": "sample"},
        {"profile_id": "coaching", "context": "Mi jefe no valora mi trabajo",
         "intervention": "¿Cómo sabes que no lo valora? ¿Qué evidencia tienes? A veces el problema no es el reconocimiento sino la comunicación.",
         "outcome": 0.5, "category": "consulta", "tags": ["trabajo", "relaciones"], "source": "sample"},
        {"profile_id": "comercial", "context": "Su producto es muy caro comparado con la competencia",
         "intervention": "Entiendo tu preocupación. Revisemos juntos el retorno que están generando nuestros clientes actuales.",
         "outcome": 0.7, "category": "objecion", "tags": ["precio", "objecion"], "source": "sample"},
        {"profile_id": "comercial", "context": "No me interesa, ya tengo proveedor",
         "intervention": "Entiendo. ¿Qué es lo que más valoras de tu proveedor actual? A veces lo que buscamos no es lo que necesitamos.",
         "outcome": 0.4, "category": "objecion", "tags": ["competencia"], "source": "sample"},
        {"profile_id": "financiero", "context": "Quiero invertir pero tengo miedo de perder",
         "intervention": "El riesgo es parte de invertir. Analicemos tu perfil de riesgo y empecemos con opciones conservadoras.",
         "outcome": 0.6, "category": "consulta", "tags": ["inversion", "riesgo"], "source": "sample"},
    ]
    logger.info("No JSON file provided. Seeding %d sample conversations.", len(samples))

    stats = await seed_from_dict(samples)
    return stats


async def seed_from_dict(records: list[dict]):
    settings = get_settings()
    qdrant = QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        check_compatibility=False,
    )
    emb = _resolve_embeddings()
    case_store = CaseStore(qdrant, emb)
    raw_store = RawStore(qdrant, emb)
    pattern_store = PatternStore(qdrant, emb)

    case_store.ensure_collection()
    raw_store.ensure_collection()
    pattern_store.ensure_collection()

    stats = {"cases": 0, "raw": 0, "patterns": 0}
    for rec in records:
        profile = rec.get("profile_id", "coaching")
        raw = RawMemory(
            profile_id=profile,
            content=f"{rec.get('context', '')} → {rec.get('intervention', '')}",
            source_type=rec.get("source", "sample"),
        )
        await raw_store.store(raw)
        stats["raw"] += 1

        case = CaseMemory(
            profile_id=profile,
            context=rec.get("context", ""),
            intervention=rec.get("intervention", ""),
            outcome=rec.get("outcome"),
            metadata=CaseMetadata(
                category=rec.get("category", "general"),
                tags=rec.get("tags", []),
                source=rec.get("source", "sample"),
                outcome=rec.get("outcome"),
            ),
        )
        await case_store.store(case)
        stats["cases"] += 1

    miner = PatternMiner(case_store, pattern_store)
    for profile in set(r.get("profile_id", "coaching") for r in records):
        mined = await miner.mine(profile, min_cases=2)
        stats["patterns"] += len(mined)

    qdrant.close()
    logger.info("Seeding complete: %s", stats)
    return stats


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] != "--sample":
        asyncio.run(seed_from_json(sys.argv[1]))
    else:
        asyncio.run(seed_sample())
