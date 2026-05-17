import pytest
from unittest.mock import AsyncMock, MagicMock
from kairos.engine.journey_architect.architect import JourneyArchitect

@pytest.mark.asyncio
async def test_validate_journey_spec_valid():
    arch = JourneyArchitect(None, None, None)
    spec = {
        "name": "Test Journey",
        "phases": [
            {
                "name": "Phase 1",
                "order_index": 1,
                "agents": [
                    {
                        "name": "Agent 1",
                        "system_prompt": "Prompt",
                        "output_schema": {
                            "structured": {
                                "required_fields": {
                                    "field1": "str"
                                }
                            }
                        },
                        "collects_fields": ["field1"],
                        "tag_mappings": {"to_next": 2}
                    }
                ]
            },
            {
                "name": "Phase 2",
                "order_index": 2,
                "agents": [
                    {
                        "name": "Agent 2",
                        "system_prompt": "Prompt 2",
                        "tag_mappings": {"complete": 99}
                    }
                ]
            }
        ]
    }
    result = await arch.validate_journey_spec(spec)
    assert result["valid"] is True
    assert len(result["errors"]) == 0

@pytest.mark.asyncio
async def test_validate_journey_spec_invalid():
    arch = JourneyArchitect(None, None, None)
    spec = {
        "name": "Invalid Journey",
        "phases": [
            {
                "name": "Phase 1",
                "order_index": 1,
                "agents": [
                    {
                        "name": "Agent 1",
                        # Missing system_prompt
                        "collects_fields": ["missing_field"],
                        "output_schema": {"structured": {"required_fields": {}}},
                        "tag_mappings": {"to_nowhere": 5}
                    }
                ]
            }
        ]
    }
    result = await arch.validate_journey_spec(spec)
    assert result["valid"] is False
    assert len(result["errors"]) > 0
    errors_str = " ".join(result["errors"])
    assert "falta 'system_prompt'" in errors_str
    assert "tag 'to_nowhere' apunta a orden 5 inexistente" in errors_str
    assert "field 'missing_field' en collects_fields no está en required_fields" in errors_str

@pytest.mark.asyncio
async def test_build_from_prompt_retry_logic():
    llm = AsyncMock()
    # First response invalid JSON, second valid
    llm.ainvoke.side_effect = [
        MagicMock(content="Invalid JSON"),
        MagicMock(content='{"journey": {"name": "Retry", "phases": [{"name": "P1", "order_index": 1, "agents": [{"name": "A1", "system_prompt": "SP"}]}]}, "gaps_detected": [], "warnings": []}')
    ]

    ms = AsyncMock()
    ms.get_methodology.return_value = "Methodology"

    arch = JourneyArchitect(llm, None, ms)
    result = await arch.build_from_prompt("coach1", "Create journey")

    assert result["journey"]["name"] == "Retry"
    assert llm.ainvoke.call_count == 2
