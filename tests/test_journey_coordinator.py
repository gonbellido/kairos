import pytest
from unittest.mock import AsyncMock, MagicMock

from kairos.engine.journey_coordinator import JourneyCoordinator
from kairos.engine.journey_engine import JourneyEngine
from kairos.db.models import ClientJourneyModel


def _make_transition(journey_id="j1", from_phase="p1", to_phase="p2",
                     condition: dict = None, priority=0, is_active=True):
    t = MagicMock()
    t.id = "t_" + (condition or {}).get("type", "x")
    t.journey_id = journey_id
    t.from_phase_id = from_phase
    t.to_phase_id = to_phase
    t.condition = condition or {}
    t.priority = priority
    t.is_active = is_active
    return t


def _mock_sf(transitions):
    sf = MagicMock()
    sess = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = transitions
    sess.execute = AsyncMock(return_value=result)
    sf.return_value.__aenter__ = AsyncMock(return_value=sess)
    sf.return_value.__aexit__ = AsyncMock()
    return sf


@pytest.mark.asyncio
async def test_no_transitions():
    sf = _mock_sf([])
    c = JourneyCoordinator(sf)
    r = await c.resolve_transition("j1", "p1", {"collected": {}, "turn_count": 5, "objective_state": {}})
    assert r is None


@pytest.mark.asyncio
async def test_turns_guard_matches():
    sf = _mock_sf([_make_transition(condition={"type": "turns", "min": 3})])
    c = JourneyCoordinator(sf)
    r = await c.resolve_transition("j1", "p1", {"collected": {}, "turn_count": 5, "objective_state": {}})
    assert r is not None
    assert r["condition_type"] == "turns"


@pytest.mark.asyncio
async def test_turns_guard_not_met():
    sf = _mock_sf([_make_transition(condition={"type": "turns", "min": 3})])
    c = JourneyCoordinator(sf)
    r = await c.resolve_transition("j1", "p1", {"collected": {}, "turn_count": 1, "objective_state": {}})
    assert r is None


@pytest.mark.asyncio
async def test_field_present_matches():
    sf = _mock_sf([_make_transition(condition={"type": "field", "field": "nombre", "op": "present"})])
    c = JourneyCoordinator(sf)
    r = await c.resolve_transition("j1", "p1", {"collected": {"nombre": "Ana"}, "turn_count": 0, "objective_state": {}})
    assert r is not None


@pytest.mark.asyncio
async def test_field_present_empty():
    sf = _mock_sf([_make_transition(condition={"type": "field", "field": "nombre", "op": "present"})])
    c = JourneyCoordinator(sf)
    r = await c.resolve_transition("j1", "p1", {"collected": {"nombre": ""}, "turn_count": 0, "objective_state": {}})
    assert r is None


@pytest.mark.asyncio
async def test_field_equals_matches():
    sf = _mock_sf([_make_transition(condition={"type": "field", "field": "ciudad", "op": "equals", "value": "Madrid"})])
    c = JourneyCoordinator(sf)
    r = await c.resolve_transition("j1", "p1", {"collected": {"ciudad": "Madrid"}, "turn_count": 0, "objective_state": {}})
    assert r is not None


@pytest.mark.asyncio
async def test_field_equals_no_match():
    sf = _mock_sf([_make_transition(condition={"type": "field", "field": "ciudad", "op": "equals", "value": "Barcelona"})])
    c = JourneyCoordinator(sf)
    r = await c.resolve_transition("j1", "p1", {"collected": {"ciudad": "Madrid"}, "turn_count": 0, "objective_state": {}})
    assert r is None


@pytest.mark.asyncio
async def test_objective_met_guard():
    sf = _mock_sf([_make_transition(condition={"type": "objective_met", "min_confidence": 0.8})])
    c = JourneyCoordinator(sf)
    r = await c.resolve_transition("j1", "p1", {
        "collected": {}, "turn_count": 0,
        "objective_state": {"a1": {"met": True, "confidence": 0.9}},
    })
    assert r is not None
    assert r["condition_type"] == "objective_met"


@pytest.mark.asyncio
async def test_objective_met_low_confidence():
    sf = _mock_sf([_make_transition(condition={"type": "objective_met", "min_confidence": 0.8})])
    c = JourneyCoordinator(sf)
    r = await c.resolve_transition("j1", "p1", {
        "collected": {}, "turn_count": 0,
        "objective_state": {"a1": {"met": True, "confidence": 0.5}},
    })
    assert r is None


@pytest.mark.asyncio
async def test_priority_order():
    low = _make_transition(to_phase="p_low", condition={"type": "turns", "min": 1}, priority=1)
    high = _make_transition(to_phase="p_high", condition={"type": "turns", "min": 1}, priority=10)
    sf = _mock_sf([high, low])
    c = JourneyCoordinator(sf)
    r = await c.resolve_transition("j1", "p1", {"collected": {}, "turn_count": 5, "objective_state": {}})
    assert r is not None
    assert r["to_phase_id"] == "p_high"


@pytest.mark.asyncio
async def test_complete_target():
    sf = _mock_sf([_make_transition(to_phase="__complete__", condition={"type": "turns", "min": 1})])
    c = JourneyCoordinator(sf)
    r = await c.resolve_transition("j1", "p1", {"collected": {}, "turn_count": 5, "objective_state": {}})
    assert r is not None
    assert r["to_phase_id"] == "__complete__"


# ── F4: fallback / jump_to_agent ──

def _mock_engine_sf():
    sf = MagicMock()
    sess = MagicMock()
    sess.execute = AsyncMock()
    sess.commit = AsyncMock()
    sf.return_value.__aenter__ = AsyncMock(return_value=sess)
    sf.return_value.__aexit__ = AsyncMock(return_value=False)
    return sf, sess


@pytest.mark.asyncio
async def test_jump_to_agent_updates_cj():
    sf, sess = _mock_engine_sf()
    mock_cj = MagicMock(spec=ClientJourneyModel)
    mock_cj.coach_id = "c1"
    mock_cj.journey_id = "j1"
    result = MagicMock()
    result.scalars.return_value.first.return_value = mock_cj
    sess.execute = AsyncMock(return_value=result)

    je = JourneyEngine(sf)
    je.get_client_journey = AsyncMock(return_value={
        "journey": {"agents": [{"id": "a_tgt", "phase_id": "p_tgt", "name": "R"}]}
    })
    await je._jump_to_agent("c1", "a_tgt")

    assert mock_cj.current_phase_id == "p_tgt"
    assert mock_cj.current_agent_id == "a_tgt"
    assert mock_cj.turn_count == 0
    sess.commit.assert_called()


@pytest.mark.asyncio
async def test_jump_to_agent_missing_agent_noops():
    sf, sess = _mock_engine_sf()
    je = JourneyEngine(sf)
    je.get_client_journey = AsyncMock(return_value={
        "journey": {"agents": []}
    })
    # Should not raise
    await je._jump_to_agent("c1", "a_missing")
    sess.commit.assert_not_called()
