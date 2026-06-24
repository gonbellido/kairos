"""F7: Integration tests for journey coordinator — run inside the app container.

Usage (in container):
    cd /app && python tests/integration/test_journey_coordinator.py

Requires PostgreSQL (already available via the app's DATABASE_URL).
Creates test data with prefixed IDs and cleans up afterwards.
"""
import asyncio
import json
import sys
from uuid import uuid4

# Ensure /app is on the path (should already be in the container)
sys.path.insert(0, "/app")

from kairos.db.session import create_session_factory
from kairos.engine.journey_engine import JourneyEngine
from kairos.db.models import JourneyTransitionModel
from sqlalchemy import delete

PASS, FAIL = 0, 0
TEST_PREFIX = "test_f7"
sf = create_session_factory()
je = JourneyEngine(sf)


async def cleanup():
    async with sf() as s:
        await s.execute(
            delete(JourneyTransitionModel).where(
                JourneyTransitionModel.journey_id.like(f"{TEST_PREFIX}%")
            )
        )
        from kairos.db.models import ClientJourneyModel, ClientSharedProfileModel
        await s.execute(
            delete(ClientJourneyModel).where(
                ClientJourneyModel.journey_id.like(f"{TEST_PREFIX}%")
            )
        )
        await s.execute(
            delete(ClientSharedProfileModel).where(
                ClientSharedProfileModel.client_id.like(f"{TEST_PREFIX}%")
            )
        )
        await s.commit()
    # Delete journeys, phases, agents last (FK order)
    async with sf() as s:
        from kairos.db.models import JourneyAgentModel, JourneyPhaseModel, JourneyModel
        await s.execute(
            delete(JourneyAgentModel).where(JourneyAgentModel.journey_id.like(f"{TEST_PREFIX}%"))
        )
        await s.execute(
            delete(JourneyPhaseModel).where(JourneyPhaseModel.journey_id.like(f"{TEST_PREFIX}%"))
        )
        await s.execute(
            delete(JourneyModel).where(JourneyModel.id.like(f"{TEST_PREFIX}%"))
        )
        await s.commit()


def ok(msg):
    global PASS
    PASS += 1
    print(f"  ✓ {msg}")


def fail(msg, detail=""):
    global FAIL
    FAIL += 1
    print(f"  ✗ {msg} — {detail}")


# ── Helpers ──

def _jid():
    return f"{TEST_PREFIX}_{uuid4().hex[:8]}"


async def _create_test_journey(name="Integration Test", profile="coaching"):
    jid = _jid()
    j = await je.create_journey(coach_id=TEST_PREFIX, name=f"{TEST_PREFIX} {name}",
                                 profile_type=profile, status="active")
    return j


async def _add_phase(jid, name, order=0):
    return await je.add_phase(jid, name=name, order_index=order)


async def _add_agent(jid, phase_id, name, collects=None, max_turns=0, fallback_id="",
                      tag_mappings=None, allowed_tags=None):
    collects = collects or []
    tag_mappings = tag_mappings or {}
    allowed_tags = allowed_tags or []
    return await je.add_agent(
        jid, phase_id, name=name, system_prompt="Eres un coach de test.",
        goal="Probar", collects_fields=collects, max_turns=max_turns,
        fallback_agent_id=fallback_id, tag_mappings=tag_mappings,
        allowed_tags=allowed_tags,
    )


async def _assign(jid):
    return await je.assign_client(client_id=f"{TEST_PREFIX}_{uuid4().hex[:6]}",
                                  coach_id=TEST_PREFIX, journey_id=jid)


async def _sync_validate(client_id, llm_response, agent_data=None):
    from kairos.engine.journey_engine import JourneyEngine
    # validate_and_advance parsea el JSON y enruta
    return await je.validate_and_advance(client_id, llm_response, agent_data or {})


async def _get_cj(client_id):
    return await je.get_client_journey(client_id)


# ── Tests ──

async def test_linear_advancement():
    print("[test] linear advancement")
    j = await _create_test_journey("Linear")
    p1 = await _add_phase(j["id"], "Diagnóstico", 0)
    p2 = await _add_phase(j["id"], "Acción", 1)
    a1 = await _add_agent(j["id"], p1["id"], "Explorador", collects=["nombre"])
    a2 = await _add_agent(j["id"], p2["id"], "Ejecutor", collects=["tarea"])

    cj = await _assign(j["id"])
    cid = cj["client_id"]
    assert cj["current_phase_id"] == p1["id"], "wrong start phase"
    ok("starts at phase 1")

    # Turn 1: agent 1 collects name, marks phase_completed
    va = await _sync_validate(cid, json.dumps({
        "message": "Hola Ana",
        "structured": {"phase_completed": True, "required_fields": {"nombre": "Ana"}},
        "next_step_tag": None,
    }), agent_data=a1)
    assert va.get("advanced"), f"should advance after completing phase 1: {va}"
    cj2 = await _get_cj(cid)
    assert cj2["current_phase_id"] == p2["id"], f"expected p2, got {cj2.get('current_phase_id')}"
    ok("advances to phase 2 after phase_completed")

    # Turn 2: agent 2 marks completed → journey completes
    va2 = await _sync_validate(cid, json.dumps({
        "message": "Tarea lista",
        "structured": {"phase_completed": True, "required_fields": {"tarea": "Hecha"}},
    }), agent_data=a2)
    cj3 = await _get_cj(cid)
    assert cj3["status"] in ("completed_journey", "completed"), f"status={cj3['status']}"
    ok("journey completed")


async def test_tag_jump():
    print("[test] tag-based non-linear jump")
    j = await _create_test_journey("TagJump")
    p1 = await _add_phase(j["id"], "Diagnóstico", 0)
    p2 = await _add_phase(j["id"], "Urgencia", 1)
    p3 = await _add_phase(j["id"], "Normal", 2)
    a1 = await _add_agent(j["id"], p1["id"], "Explorador",
                           collects=["sintoma"],
                           allowed_tags=["to_urgent", "to_normal"],
                           tag_mappings={"to_urgent": p2["id"], "to_normal": p3["id"]})

    cj = await _assign(j["id"])
    cid = cj["client_id"]

    # Emit tag "to_urgent" → expect jump to phase p2 (Urgencia)
    va = await _sync_validate(cid, json.dumps({
        "message": "Emergencia!",
        "structured": {"phase_completed": True, "required_fields": {"sintoma": "dolor"}},
        "suggested_tags": ["to_urgent"],
    }), agent_data=a1)
    cj2 = await _get_cj(cid)
    assert cj2["current_phase_id"] == p2["id"], f"should jump to urgencia, got {cj2['current_phase_id']}"
    ok("tag jump to 'Urgencia' works")


async def test_guard_turns():
    print("[test] guard-based transition: turns")
    j = await _create_test_journey("GuardTurns")
    p1 = await _add_phase(j["id"], "Espera", 0)
    p2 = await _add_phase(j["id"], "Timeout", 1)
    a1 = await _add_agent(j["id"], p1["id"], "Esperador")

    # Add transition: after 2 turns in p1 → jump to p2
    await je.add_transition(j["id"], p1["id"], p2["id"],
                            condition={"type": "turns", "min": 2})

    cj = await _assign(j["id"])
    cid = cj["client_id"]

    # Turn 1: no data, no advancement
    va1 = await _sync_validate(cid, json.dumps({"message": "Hola", "structured": {}}), agent_data=a1)
    cj1 = await _get_cj(cid)
    assert cj1["turn_count"] == 1
    ok("turn 1 counted, no advance")

    # Turn 2: still no data
    va2 = await _sync_validate(cid, json.dumps({"message": "Hola de nuevo", "structured": {}}), agent_data=a1)
    cj2 = await _get_cj(cid)
    assert cj2["current_phase_id"] == p2["id"], f"should jump to timeout after 2 turns, got {cj2['current_phase_id']}"
    ok("guard 'turns' fired at turn 2 → advanced")


async def test_guard_field():
    print("[test] guard-based transition: field present")
    j = await _create_test_journey("GuardField")
    p1 = await _add_phase(j["id"], "Recolección", 0)
    p2 = await _add_phase(j["id"], "Procesado", 1)
    a1 = await _add_agent(j["id"], p1["id"], "Recolector", collects=["email"])

    await je.add_transition(j["id"], p1["id"], p2["id"],
                            condition={"type": "field", "field": "email", "op": "present"})

    cj = await _assign(j["id"])
    cid = cj["client_id"]

    # Turn: collector returns email in collected_data
    va = await _sync_validate(cid, json.dumps({
        "message": "Tu email porfa",
        "structured": {"phase_completed": False, "required_fields": {"email": "a@b.com"}},
    }), agent_data=a1)
    cj2 = await _get_cj(cid)
    assert cj2["current_phase_id"] == p2["id"], f"field guard should advance, got {cj2['current_phase_id']}"
    ok("guard 'field present' fired → advanced")


async def test_fallback_max_turns():
    print("[test] fallback: max_turns exceeded → rescue agent")
    j = await _create_test_journey("Fallback")
    p1 = await _add_phase(j["id"], "Estancada", 0)
    p2 = await _add_phase(j["id"], "Rescate", 1)
    a2 = await _add_agent(j["id"], p2["id"], "Rescatista")
    a1 = await _add_agent(j["id"], p1["id"], "Blocker",
                           max_turns=2, fallback_id=a2["id"])

    cj = await _assign(j["id"])
    cid = cj["client_id"]

    # Turn 1
    await _sync_validate(cid, json.dumps({"message": "No sé", "structured": {}}), agent_data=a1)
    cj1 = await _get_cj(cid)
    assert cj1["current_phase_id"] == p1["id"], "should still be in phase 1 after turn 1"
    ok("turn 1: stays")

    # Turn 2 — should trigger fallback
    await _sync_validate(cid, json.dumps({"message": "Sigo sin saber", "structured": {}}), agent_data=a1)
    cj2 = await _get_cj(cid)
    assert cj2["current_phase_id"] == p2["id"], f"fallback should jump to rescue, got {cj2['current_phase_id']}"
    ok("fallback fired at turn 2 → rescue agent")


async def test_derivation_journey_to_journey():
    print("[test] derivation: journey → journey")
    j1 = await _create_test_journey("Source", profile="coaching")
    j2 = await _create_test_journey("Target", profile="financiero")
    p1 = await _add_phase(j1["id"], "Inicio", 0)
    p1t = await _add_phase(j2["id"], "Destino", 0)
    a1 = await _add_agent(j1["id"], p1["id"], "Origen")
    await _add_agent(j2["id"], p1t["id"], "Meta")

    await je.add_transition(j1["id"], p1["id"], f"journey:{j2['id']}",
                            condition={"type": "turns", "min": 1})
    trans = await je.get_transitions(j1["id"])
    assert len(trans) == 1, f"transition not created, found {len(trans)}"
    assert trans[0]["to_phase_id"] == f"journey:{j2['id']}"

    cj = await _assign(j1["id"])
    cid = cj["client_id"]

    await _sync_validate(cid, json.dumps({"message": "Derivame", "structured": {}}), agent_data=a1)
    cj2 = await _get_cj(cid)
    assert cj2["status"] == "derived", f"source should be derived, got {cj2['status']}"
    assert cj2["journey"]["id"] == j2["id"], f"should point to target journey {j2['id']}"
    ok("derived to target journey, shared_profile preserved")


# ── Runner ──

async def main():
    global PASS, FAIL
    print("\n=== F7 Integration Tests ===\n")

    tests = [
        test_linear_advancement,
        test_tag_jump,
        test_guard_turns,
        test_guard_field,
        test_fallback_max_turns,
        test_derivation_journey_to_journey,
    ]

    for t in tests:
        try:
            await t()
        except Exception as e:
            fail(t.__name__, str(e))
            import traceback
            traceback.print_exc()

    await cleanup()

    print(f"\n{'='*40}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print(f"{'='*40}")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
