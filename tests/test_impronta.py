import pytest
from kairos.core.impronta import Impronta, ImprontaConstraints


def test_impronta_defaults():
    i = Impronta()
    assert i.directividad == 0.5
    assert i.emocionalidad == 0.5
    assert i.analiticidad == 0.5
    assert i.riesgo == 0.5


def test_impronta_update():
    i = Impronta(directividad=0.3)
    i2 = i.update({"directividad": 0.9})
    assert i2.directividad == 0.9
    assert i2.emocionalidad == 0.5


def test_impronta_constraints_clamp():
    min_i = Impronta(directividad=0.2, emocionalidad=0.2, analiticidad=0.2, riesgo=0.2)
    max_i = Impronta(directividad=0.8, emocionalidad=0.8, analiticidad=0.8, riesgo=0.8)
    cs = ImprontaConstraints(min=min_i, max=max_i)
    i = Impronta(directividad=0.1, emocionalidad=0.9, analiticidad=0.5, riesgo=0.5)
    clamped = cs.clamp(i)
    assert clamped.directividad == 0.2
    assert clamped.emocionalidad == 0.8
    assert clamped.analiticidad == 0.5
