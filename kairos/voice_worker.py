"""Fase L: Voice Worker entry point. Runs as separate process.
Usage: python -m kairos.voice_worker
"""

import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("kairos.voice")

if __name__ == "__main__":
    from livekit import agents
    from kairos.engine.voice_agent import create_agent

    server = create_agent()
    logger.info("Starting KAIROS Voice Agent on LiveKit...")
    agents.cli.run_app(server)
