#!/usr/bin/env python3
import asyncio
from qdrant_client import QdrantClient
from kairos.config import get_settings
from kairos.memory.stores import CaseStore
from kairos.memory.embeddings import OpenAIEmbeddingProvider
from kairos.core.memory import CaseMemory, CaseMetadata


async def seed() -> None:
    settings = get_settings()
    qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    emb = OpenAIEmbeddingProvider()
    store = CaseStore(qdrant, emb)
    store.ensure_collection()

    samples = [
        CaseMemory(profile_id="coaching", context="No sé qué hacer con mi carrera, me siento estancado",
                   intervention="¿Qué significa exactamente 'estancado' para ti? ¿Es falta de movimiento o falta de dirección?",
                   outcome=0.8, metadata=CaseMetadata(category="consulta", tags=["carrera", "proposito"])),
        CaseMemory(profile_id="coaching", context="Mi equipo no rinde como esperaba",
                   intervention="¿Cómo defines 'rendir'? ¿Y cómo sabes que no está rindiendo?",
                   outcome=0.6, metadata=CaseMetadata(category="consulta", tags=["liderazgo"])),
        CaseMemory(profile_id="comercial", context="Su producto es muy caro comparado con la competencia",
                   intervention="Entiendo tu preocupación. Revisemos juntos el retorno que generan nuestros clientes actuales.",
                   outcome=0.7, metadata=CaseMetadata(category="objecion", tags=["precio", "objecion"])),
    ]

    for c in samples:
        cid = await store.store(c)
        print(f"Stored case {cid} for '{c.profile_id}'")


if __name__ == "__main__":
    asyncio.run(seed())
