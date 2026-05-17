import pytest
from kairos.engine.state_classifier import StateClassifier


@pytest.mark.asyncio
async def test_classify_neutral(classifier):
    result = await classifier.classify("Hola, quería saber más sobre sus servicios")
    assert result["emocion"] == "neutral"
    assert result["tono"] == "friendly"
    assert result["intencion"] in ("consulta", "general")


@pytest.mark.asyncio
async def test_classify_negative(classifier):
    result = await classifier.classify("Estoy muy frustrado con este servicio, es pésimo")
    assert result["emocion"] == "negative"
    assert result["tono"] == "neutral"


@pytest.mark.asyncio
async def test_classify_urgent(classifier):
    result = await classifier.classify("ES URGENTE, necesito ayuda inmediata")
    assert result["urgencia"] > 0.0
    assert result["emocion"] == "urgent"


@pytest.mark.asyncio
async def test_classify_risk(classifier):
    result = await classifier.classify("Esto es una crisis, perdí todo, necesito un abogado")
    assert result["riesgo"] > 0
