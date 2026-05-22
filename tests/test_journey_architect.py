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


@pytest.mark.asyncio
async def test_validate_agent_output_valid():
    from kairos.engine.journey_engine import validate_agent_output
    schema = {
        "structured": {"required_fields": {"name": "string", "age": "number"}}
    }
    output = {"structured": {"name": "Juan", "age": 30}}
    result = validate_agent_output(schema, output)
    assert result["valid"] is True


@pytest.mark.asyncio
async def test_validate_agent_output_missing_field():
    from kairos.engine.journey_engine import validate_agent_output
    schema = {
        "structured": {"required_fields": {"name": "string", "age": "number"}}
    }
    output = {"structured": {"name": "Juan"}}
    result = validate_agent_output(schema, output)
    assert result["valid"] is False
    assert any("age" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_validate_agent_output_wrong_type():
    from kairos.engine.journey_engine import validate_agent_output
    schema = {
        "structured": {"required_fields": {"age": "number"}}
    }
    output = {"structured": {"age": "treinta"}}
    result = validate_agent_output(schema, output)
    assert result["valid"] is False
    assert any("number" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_validate_agent_output_empty_schema():
    from kairos.engine.journey_engine import validate_agent_output
    result = validate_agent_output({}, {"structured": {"name": "Juan"}})
    assert result["valid"] is True


@pytest.mark.asyncio
async def test_validate_journey_spec_tag_mappings():
    from kairos.engine.journey_architect.architect import JourneyArchitect
    arch = JourneyArchitect(None, None, None)
    spec = {
        "name": "Tag Test",
        "phases": [
            {
                "name": "P1", "order_index": 1,
                "agents": [{"name": "A1", "system_prompt": "SP",
                            "tag_mappings": {"to_p2": 2, "to_p3": 3}}]
            },
            {
                "name": "P2", "order_index": 2,
                "agents": [{"name": "A2", "system_prompt": "SP"}]
            },
            {
                "name": "P3", "order_index": 3,
                "agents": [{"name": "A3", "system_prompt": "SP",
                            "tag_mappings": {"complete": 99}}]
            }
        ]
    }
    result = await arch.validate_journey_spec(spec)
    assert result["valid"] is True
    assert len(result["errors"]) == 0


@pytest.mark.asyncio
async def test_validate_journey_spec_bad_tag():
    from kairos.engine.journey_architect.architect import JourneyArchitect
    arch = JourneyArchitect(None, None, None)
    spec = {
        "name": "Bad Tag",
        "phases": [
            {
                "name": "P1", "order_index": 1,
                "agents": [{"name": "A1", "system_prompt": "SP",
                            "tag_mappings": {"to_nowhere": 99}}]
            }
        ]
    }
    result = await arch.validate_journey_spec(spec)
    assert result["valid"] is True  # 99 is valid (journey_complete)


@pytest.mark.asyncio
async def test_validate_journey_spec_tag_inexistent_order():
    from kairos.engine.journey_architect.architect import JourneyArchitect
    arch = JourneyArchitect(None, None, None)
    spec = {
        "name": "Bad Tag",
        "phases": [
            {
                "name": "P1", "order_index": 1,
                "agents": [{"name": "A1", "system_prompt": "SP",
                            "tag_mappings": {"to_p5": 5}}]
            }
        ]
    }
    result = await arch.validate_journey_spec(spec)
    assert result["valid"] is False
    assert any("5" in e for e in result["errors"])
