#!/usr/bin/env python3
"""Batch pattern mining job. Run as cron: python scripts/mine_patterns.py"""
import asyncio
import logging

from qdrant_client import QdrantClient
from kairos.config import get_settings
from kairos.memory.stores import CaseStore, PatternStore
from kairos.memory.embeddings import OpenAIEmbeddingProvider
from kairos.engine.pattern_miner import PatternMiner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    settings = get_settings()
    qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    emb = OpenAIEmbeddingProvider()

    case_store = CaseStore(qdrant, emb)
    pattern_store = PatternStore(qdrant, emb)
    miner = PatternMiner(case_store, pattern_store)

    for profile_id in ["coaching", "comercial", "financiero"]:
        patterns = await miner.mine(profile_id)
        logger.info("Profile %s: %d patterns mined", profile_id, len(patterns))

    qdrant.close()


if __name__ == "__main__":
    asyncio.run(main())
