import pytest

from kairos.engine.objective_evaluator import ObjectiveEvaluator


@pytest.mark.asyncio
async def test_deterministic_all_fields_present():
    agent = {"id": "a1", "collects_fields": ["nombre", "edad"]}
    collected = {"nombre": "Ana", "edad": 30}
    r = await ObjectiveEvaluator().evaluate(agent, collected)
    assert r["met"] is True
    assert r["missing"] == []
    assert r["mode"] == "deterministic"
    assert r["confidence"] == 1.0
    assert "ts" in r


@pytest.mark.asyncio
async def test_deterministic_missing_and_empty_fields():
    agent = {"id": "a1", "collects_fields": ["nombre", "edad", "ciudad"]}
    collected = {"nombre": "Ana", "edad": "", "ciudad": None}
    r = await ObjectiveEvaluator().evaluate(agent, collected)
    assert r["met"] is False
    assert set(r["missing"]) == {"edad", "ciudad"}


@pytest.mark.asyncio
async def test_collects_fields_as_json_string():
    agent = {"id": "a1", "collects_fields": '["nombre"]'}
    r = await ObjectiveEvaluator().evaluate(agent, {"nombre": "Ana"})
    assert r["met"] is True


@pytest.mark.asyncio
async def test_no_fields_no_judge_falls_back():
    agent = {"id": "a1", "collects_fields": [], "goal": "Cerrar la sesión"}
    r = await ObjectiveEvaluator().evaluate(agent, {})
    assert r["met"] is False
    assert r["mode"] == "deterministic_fallback"


@pytest.mark.asyncio
async def test_llm_mode_uses_judge():
    async def judge(_prompt):
        return '{"met": true, "confidence": 0.8, "missing": []}'

    agent = {"id": "a1", "collects_fields": [], "goal": "Cerrar"}
    r = await ObjectiveEvaluator(llm_judge=judge).evaluate(agent, {}, transcript="...")
    assert r["met"] is True
    assert r["confidence"] == 0.8
    assert r["mode"] == "llm"


@pytest.mark.asyncio
async def test_hybrid_deterministic_met_short_circuits():
    called = {"n": 0}

    async def judge(_prompt):
        called["n"] += 1
        return '{"met": false, "confidence": 0.1, "missing": []}'

    agent = {"id": "a1", "collects_fields": ["nombre"], "objective_eval": {"mode": "hybrid"}}
    r = await ObjectiveEvaluator(llm_judge=judge).evaluate(agent, {"nombre": "Ana"})
    assert r["met"] is True
    assert r["mode"] == "hybrid"
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_llm_judge_handles_code_fence():
    async def judge(_prompt):
        return '```json\n{"met": true, "confidence": 0.9, "missing": []}\n```'

    agent = {"id": "a1", "collects_fields": [], "goal": "x"}
    r = await ObjectiveEvaluator(llm_judge=judge).evaluate(agent, {})
    assert r["met"] is True
    assert r["confidence"] == 0.9


@pytest.mark.asyncio
async def test_llm_judge_failure_falls_back():
    async def judge(_prompt):
        raise RuntimeError("boom")

    agent = {"id": "a1", "collects_fields": [], "goal": "x"}
    r = await ObjectiveEvaluator(llm_judge=judge).evaluate(agent, {})
    assert r["met"] is False
    assert r["mode"] == "deterministic_fallback"
