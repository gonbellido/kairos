import pytest
from kairos.engine.profile_engine import ProfileEngine
from kairos.core.exceptions import ProfileNotFoundError


@pytest.mark.asyncio
async def test_load_coaching(profile_engine):
    p = await profile_engine.get_profile("coaching")
    assert p.id == "coaching"
    assert p.name == "Coach Ontológico"
    assert p.default_impronta.directividad == 0.3
    assert p.default_impronta.emocionalidad == 0.8
    assert p.default_impronta.analiticidad == 0.3


@pytest.mark.asyncio
async def test_load_nonexistent(profile_engine):
    with pytest.raises(ProfileNotFoundError):
        await profile_engine.get_profile("no_such_profile")


@pytest.mark.asyncio
async def test_resolve_impronta_with_overrides(profile_engine):
    i = await profile_engine.resolve_impronta("coaching", {"directividad": 0.9})
    assert i.directividad == 0.9
    assert i.emocionalidad == 0.8
