import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from kairos.agents.orchestrator import KairosRuntime
from kairos.core.state import AgentState

@pytest.fixture
def mock_runtime_deps():
    with patch("kairos.agents.orchestrator.QdrantClient"),          patch("kairos.agents.orchestrator.create_llm"),          patch("kairos.agents.orchestrator.create_eval_llm"),          patch("kairos.agents.orchestrator.RawStore"),          patch("kairos.agents.orchestrator.CaseStore"),          patch("kairos.agents.orchestrator.PatternStore"),          patch("kairos.agents.orchestrator.ExecutionStore"),          patch("kairos.agents.orchestrator.KnowledgeStore"),          patch("kairos.agents.orchestrator.ClientStore"):
        yield

@pytest.mark.asyncio
async def test_orchestrator_without_journey(mock_runtime_deps):
    # Setup runtime without journey_engine
    runtime = KairosRuntime()
    runtime.journey_engine = None

    # Mock build_graph to return a simple mock graph
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"final_response": "Hello", "confidence": 1.0})
    runtime._build_graph = MagicMock(return_value=mock_graph)

    result = await runtime.run(
        session_id="test_session",
        profile_id="coaching",
        message="Hello",
        context={"client_id": "client_123"}
    )

    assert result["final_response"] == "Hello"
    # Verify journey_engine was not called
    assert runtime.journey_engine is None

@pytest.mark.asyncio
async def test_orchestrator_with_active_journey(mock_runtime_deps):
    # Mock journey_engine
    mock_je = AsyncMock()
    mock_je.get_client_journey = AsyncMock(return_value={
        "status": "active",
        "journey": {"name": "Test Journey", "agents": [{"id": "agent_1"}]},
        "current_agent_id": "agent_1"
    })

    runtime = KairosRuntime()
    runtime.journey_engine = mock_je

    # Mock build_graph
    mock_graph = MagicMock()
    async def side_effect(initial_state):
        # Verify journey_context was loaded into initial state
        assert initial_state.get("journey_context") is not None
        assert initial_state["journey_context"]["status"] == "active"
        return {"final_response": "Journey Response", "confidence": 1.0}

    mock_graph.ainvoke = AsyncMock(side_effect=side_effect)
    runtime._build_graph = MagicMock(return_value=mock_graph)

    result = await runtime.run(
        session_id="test_session",
        profile_id="coaching",
        message="Hello",
        context={"client_id": "client_123"}
    )

    assert result["final_response"] == "Journey Response"
    mock_je.get_client_journey.assert_called_with("client_123")

@pytest.mark.asyncio
async def test_journey_nodes_logic():
    from kairos.agents.nodes.journey_agent import journey_inject_node, journey_advance_node

    mock_je = AsyncMock()
    mock_je.compose_agent_prompt = AsyncMock(return_value="Specialized Prompt")
    mock_je.validate_and_advance = AsyncMock(return_value={"advanced": True, "message": "Modified Response"})
    mock_je.get_client_journey = AsyncMock(return_value={"status": "active", "current_agent_id": "agent_2"})

    state: AgentState = {
        "message": "Hi",
        "journey_context": {"status": "active", "journey": {"agents": [{"id": "agent_1"}]}, "current_agent_id": "agent_1"},
        "context": {"client_id": "c1"},
        "llm_response": "I'm done",
        "next_agent": "worker"
    }

    # Test inject node
    inject_result = await journey_inject_node(state, mock_je)
    assert inject_result["journey_system_prompt"] == "Specialized Prompt"

    # Test advance node
    advance_result = await journey_advance_node(state, mock_je)
    assert advance_result["journey_advanced"] is True
    assert advance_result["journey_context"]["current_agent_id"] == "agent_2"
    assert advance_result["final_response"] == "Modified Response"


@pytest.mark.asyncio
async def test_clone_journey():
    from kairos.engine.journey_engine import JourneyEngine
    from kairos.db.session import create_session_factory
    sf = create_session_factory()
    je = JourneyEngine(sf)

    j = await je.create_journey(coach_id="test", name="Original",
                                description="Desc", objective="Obj",
                                profile_type="coaching")
    jid = j["id"]
    p = await je.add_phase(jid, name="Fase 1", objective="Obj 1", order_index=1)
    await je.add_agent(jid, p["id"], name="Agent 1", system_prompt="SP",
                       collects_fields=["name"], output_schema={"structured": {"required_fields": {"name": "str"}}},
                       tag_mappings={"next": 2})

    cloned = await je.clone_journey(jid)
    assert cloned is not None
    assert cloned["id"] != jid
    assert "Copia de Original" in cloned["name"]
    assert cloned["status"] == "draft"
    assert len(cloned.get("phases", [])) == 1
    assert len(cloned.get("agents", [])) == 1
    assert cloned["agents"][0]["name"] == "Agent 1"

    original = await je.get_journey(jid)
    assert original["name"] == "Original"

    await je.delete_journey(jid)
    await je.delete_journey(cloned["id"])


@pytest.mark.asyncio
async def test_clone_nonexistent_journey():
    from kairos.engine.journey_engine import JourneyEngine
    from kairos.db.session import create_session_factory
    sf = create_session_factory()
    je = JourneyEngine(sf)
    result = await je.clone_journey("nonexistent")
    assert result is None
