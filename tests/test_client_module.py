import pytest
from kairos.core.client import (
    ClientProfile, ClientState, ClientProgress, SignalMetrics,
    ClientObjective, ClientInsight, ClientPattern, Alert,
)
from kairos.engine.client_synthesizer import ClientSynthesizer
from kairos.memory.scoring import ClientSimilarityScorer, ScoringContext, ScoringEngine
from kairos.core.memory import CaseMemory, ScoredCase


class TestClientModels:
    def test_client_profile_defaults(self):
        p = ClientProfile(id="c1", nombre="Test")
        assert p.estado_actual.emocional == "neutral"
        assert p.estado_actual.claridad == 0.5
        assert p.progreso.score_global == 0.0
        assert len(p.objetivos) == 0

    def test_client_objective(self):
        o = ClientObjective(titulo="Mejorar comunicación")
        assert o.activo is True
        assert o.titulo == "Mejorar comunicación"

    def test_alert_creation(self):
        a = Alert(tipo="alta_resistencia", nivel="high", mensaje="Cliente en crisis", cliente_id="c1")
        assert a.accion == "notify_coach"
        assert a.activa is True

    def test_signal_metrics_progress(self):
        sm = SignalMetrics(claridad=0.8, accion=0.6, apertura=0.7, consistencia=0.9)
        p = ClientProgress(score_global=0.75, senales=sm)
        assert p.score_global == 0.75
        assert p.senales.claridad == 0.8


class TestClientSynthesizer:
    @pytest.mark.asyncio
    async def test_apply_synthesis_updates_profile(self):
        synth = ClientSynthesizer(llm=None)
        profile = ClientProfile(id="c1", nombre="Ana")

        # Mock the internal _llm call — test apply_synthesis directly
        synthesis = {
            "estado_emocional": "ansioso",
            "claridad": 0.3,
            "energia": 0.4,
            "resistencia": 0.7,
            "insights": [{"tipo": "revelacion", "contenido": "Tiene miedo al cambio"}],
            "patrones": [{"patron": "lenguaje negativo", "frecuencia": 3}],
            "avances": [],
        }

        updated = synth.apply_synthesis(profile, synthesis)
        assert updated.estado_actual.emocional == "ansioso"
        assert updated.estado_actual.claridad == 0.3
        assert updated.estado_actual.resistencia == 0.7
        assert len(updated.insights) == 1
        assert len(updated.patrones_detectados) == 1
        assert updated.patrones_detectados[0].patron == "lenguaje negativo"
        assert updated.progreso.score_global > 0

    @pytest.mark.asyncio
    async def test_apply_synthesis_increments_patterns(self):
        synth = ClientSynthesizer(llm=None)
        profile = ClientProfile(id="c1", nombre="Ana")
        profile.patrones_detectados.append(ClientPattern(patron="lenguaje negativo", frecuencia=1))

        synthesis = {
            "patrones": [{"patron": "lenguaje negativo", "frecuencia": 1}],
        }
        updated = synth.apply_synthesis(profile, synthesis)
        assert len(updated.patrones_detectados) == 1
        assert updated.patrones_detectados[0].frecuencia == 2


class TestClientScoring:
    @pytest.mark.asyncio
    async def test_client_similarity_scorer(self):
        scorer = ClientSimilarityScorer()
        ctx = ScoringContext(state={"emocion": "negative", "intencion": "consulta", "tono": "neutral"})
        matching = ScoredCase(
            case=CaseMemory(profile_id="t", context="x", intervention="y",
                            state_classification={"emocion": "negative", "intencion": "consulta", "tono": "neutral"}),
            semantic_score=0.5,
        )
        mismatching = ScoredCase(
            case=CaseMemory(profile_id="t", context="x", intervention="y",
                            state_classification={"emocion": "positive", "intencion": "compra", "tono": "friendly"}),
            semantic_score=0.5,
        )
        score_match = await scorer.score(matching, ctx)
        score_mismatch = await scorer.score(mismatching, ctx)
        assert score_match > score_mismatch

    @pytest.mark.asyncio
    async def test_client_similarity_without_state(self):
        scorer = ClientSimilarityScorer()
        ctx = ScoringContext()
        case = ScoredCase(
            case=CaseMemory(profile_id="t", context="x", intervention="y"),
            semantic_score=0.5,
        )
        score = await scorer.score(case, ctx)
        assert score == 0.5
