#!/usr/bin/env python3
"""Load sample experiences into Qdrant for testing."""
import asyncio
import json
from pathlib import Path

from qdrant_client import QdrantClient
from phronos.config import get_settings
from phronos.memory.store import ExperienceStore
from phronos.memory.embeddings import OpenAIEmbeddingProvider
from phronos.core.experience import Experience, ExperienceMetadata


async def seed() -> None:
    settings = get_settings()

    qdrant = QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
    )
    embeddings = OpenAIEmbeddingProvider()
    store = ExperienceStore(qdrant, embeddings)
    store.ensure_collection()

    # Load from fixtures or use defaults
    fixtures_path = Path("./tests/fixtures/sample_experiences.json")
    if fixtures_path.exists():
        with open(fixtures_path) as f:
            samples = json.load(f)
    else:
        samples = [
            {
                "profile_id": "coaching",
                "input_text": "No sé qué hacer con mi carrera, me siento estancado",
                "output_text": "¿Qué significa exactamente 'estancado' para ti? ¿Es falta de movimiento o falta de dirección?",
                "category": "consulta",
                "tags": ["carrera", "propósito"],
                "outcome": 0.8,
            },
            {
                "profile_id": "coaching",
                "input_text": "Mi equipo no rinde como esperaba",
                "output_text": "¿Cómo defines 'rendir'? ¿Y cómo sabes que no está rindiendo? A veces lo que medimos no es lo que importa.",
                "category": "consulta",
                "tags": ["liderazgo", "equipo"],
                "outcome": 0.6,
            },
            {
                "profile_id": "comercial",
                "input_text": "Su producto es muy caro comparado con la competencia",
                "output_text": "Entiendo tu preocupación por el precio. ¿Te parece bien si revisamos juntos el retorno que están generando nuestros clientes actuales? Muchas veces el valor está en lo que se evita, no solo en lo que se paga.",
                "category": "objecion",
                "tags": ["precio", "objecion"],
                "outcome": 0.7,
            },
        ]

    for s in samples:
        exp = Experience(
            profile_id=s["profile_id"],
            input_text=s["input_text"],
            output_text=s["output_text"],
            metadata=ExperienceMetadata(
                category=s.get("category", "general"),
                tags=s.get("tags", []),
                outcome=s.get("outcome"),
                source="synthetic",
            ),
        )
        exp_id = await store.store(exp)
        print(f"Stored experience {exp_id} for profile '{exp.profile_id}'")

    print(f"Seeded {len(samples)} experiences.")


if __name__ == "__main__":
    asyncio.run(seed())
