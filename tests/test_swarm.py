"""Tests for KAIROS Swarm module."""
import os
import pytest


@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY") and not os.environ.get("LLM_API_KEY"),
                    reason="Requires API key")
def test_swarm_imports():
    from kairos.agents.swarm import create_kairos_swarm, run_swarm_turn
    assert callable(create_kairos_swarm)
    assert callable(run_swarm_turn)
