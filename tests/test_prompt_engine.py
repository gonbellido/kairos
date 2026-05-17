import pytest
from kairos.core.profile import Profile
from kairos.core.impronta import Impronta
from kairos.core.memory import CaseMemory, CaseMetadata, RankedCase, PatternMemory
from kairos.engine.prompt_engine import PromptEngine


@pytest.mark.asyncio
async def test_basic_prompt():
    e = PromptEngine()
    profile = Profile(id="test", name="T", description="D",
                      system_prompt_template="Eres {{ profile_name }}. Dir: {{ directividad }}.",
                      default_impronta=Impronta(directividad=0.7))
    prompt = await e.build(profile=profile, impronta=Impronta(directividad=0.7),
                           state_classification={"riesgo": 0.5, "emocion": "neutral", "urgencia": 0.2, "intencion": "consulta", "tono": "polite"},
                           cases=[], patterns=[], knowledge_docs=[], message="Hola")
    assert "Eres T" in prompt
    assert "Dir: 0.7" in prompt
    assert "Hola" in prompt


@pytest.mark.asyncio
async def test_prompt_with_cases():
    e = PromptEngine()
    profile = Profile(id="t", name="X", description="D", system_prompt_template="Tpl", default_impronta=Impronta())
    case = RankedCase(case=CaseMemory(profile_id="t", context="prev ctx", intervention="prev int", metadata=CaseMetadata(category="t")), composite_score=0.85)
    prompt = await e.build(profile=profile, impronta=Impronta(), state_classification=None,
                           cases=[case], patterns=[], knowledge_docs=[], message="new")
    assert "prev ctx" in prompt
    assert "prev int" in prompt
    assert "0.85" in prompt


@pytest.mark.asyncio
async def test_prompt_with_patterns():
    e = PromptEngine()
    profile = Profile(id="t", name="X", description="D", system_prompt_template="Tpl", default_impronta=Impronta())
    pattern = PatternMemory(profile_id="t", pattern_type="success", title="Repeat wins", description="X", statistical_signal=0.9, frequency=10)
    prompt = await e.build(profile=profile, impronta=Impronta(), state_classification=None,
                           cases=[], patterns=[pattern], knowledge_docs=[], message="hi")
    assert "Repeat wins" in prompt
    assert "0.90" in prompt
