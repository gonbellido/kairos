"""Tests for emotional TTS mapping."""

from kairos.engine.emotional_tts import (
    get_voice_style, get_emotional_prompt_extension, sentiment_from_state
)


def test_get_voice_style_positive():
    style = get_voice_style("positive")
    assert "upbeat" in style["tone"]


def test_get_voice_style_negative():
    style = get_voice_style("negative")
    assert "empathetic" in style["tone"]


def test_get_voice_style_unknown_falls_to_neutral():
    style = get_voice_style("nonexistent")
    assert style["tone"] == "warm, natural, conversational"


def test_prompt_extension_low_confidence():
    ext = get_emotional_prompt_extension("negative", confidence=0.1)
    assert ext == ""


def test_prompt_extension_high_confidence():
    ext = get_emotional_prompt_extension("urgent", confidence=0.8)
    assert "calma" in ext.lower()


def test_sentiment_from_state_empty():
    assert sentiment_from_state({}) == "neutral"


def test_sentiment_from_state_risk():
    assert sentiment_from_state({"riesgo": 0.8}) == "urgent"


def test_sentiment_from_state_emotion():
    assert sentiment_from_state({"emocion": "positive"}) == "positive"
