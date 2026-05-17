"""Etapa 10: Classifier tests + integration notes."""

import pytest
from kairos.agents.classifier import classify, MessagePath, InputChannel, detect_risk


class TestClassifier:

    def test_greeting_fast(self):
        assert classify("hola").path == MessagePath.FAST
        assert classify("buenos días").path == MessagePath.FAST
        assert classify("buenas tardes coach").path == MessagePath.FAST

    def test_short_statement_fast(self):
        r = classify("ok gracias")
        assert r.path == MessagePath.FAST
        assert r.detected_intent == "greeting"

    def test_journey_data_fast(self):
        assert classify("Gonzalo", journey_phase_expects_data=True).path == MessagePath.FAST
        assert classify("masculino", journey_phase_expects_data=True).path == MessagePath.FAST
        assert classify("15 enero 1990", journey_phase_expects_data=True).path == MessagePath.FAST

    def test_deep_triggers(self):
        assert classify("¿qué es la bioneuroemoción?").path == MessagePath.DEEP
        assert classify("siento que tengo un bloqueo").path == MessagePath.DEEP
        assert classify("necesito trabajar mi ansiedad").path == MessagePath.DEEP
        assert classify("tengo un problema con mi pareja").path == MessagePath.DEEP

    def test_memory_triggers(self):
        assert classify("recuerdas lo que hablamos?").needs_memory is True
        assert classify("dijiste que me ayudarías").needs_memory is True
        assert classify("ayer hablamos de mi miedo").needs_memory is True

    def test_simple_question_fast(self):
        r = classify("¿cómo estás?")
        assert r.path == MessagePath.FAST
        assert r.detected_intent == "question"

    def test_voice_path(self):
        assert classify("", channel=InputChannel.LIVEKIT).path == MessagePath.VOICE
        assert classify("hola", channel=InputChannel.LIVEKIT).path == MessagePath.VOICE

    def test_risk_detection(self):
        assert detect_risk("hacerme daño") == "high"
        assert detect_risk("no puedo más con esto") == "medium"
        assert classify("suicidio").risk_level == "high"
        assert classify("llorar mucho").risk_level == "medium"
        assert classify("hola").risk_level == "low"

    def test_deep_with_rag_flags(self):
        r = classify("necesito ayuda profesional")
        assert r.path == MessagePath.DEEP
        assert r.needs_rag is True
        assert r.needs_memory is True

    def test_deep_triggers_beat_word_count(self):
        # "siento que" is deep trigger even though message is short
        assert classify("siento que").path == MessagePath.DEEP
        # "dijiste" is memory trigger even for short messages
        assert classify("dijiste eso").needs_memory is True
