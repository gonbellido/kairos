"""Emotional TTS — maps classifier sentiment to voice parameters and prompt style."""

SENTIMENT_MAP = {
    "positive": {
        "tone": "upbeat, warm, encouraging",
        "speed": "normal",
        "prompt_style": "Mantén un tono alegre y alentador. Celebra el progreso del cliente.",
    },
    "negative": {
        "tone": "soft, empathetic, gentle",
        "speed": "slightly slower",
        "prompt_style": "Sé especialmente empático y comprensivo. Usa un tono suave. Valida los sentimientos del cliente.",
    },
    "urgent": {
        "tone": "calm, steady, reassuring",
        "speed": "slightly slower, deliberate",
        "prompt_style": "Mantén la calma. Habla con claridad y seguridad. No entres en pánico. Guía al cliente paso a paso.",
    },
    "neutral": {
        "tone": "warm, natural, conversational",
        "speed": "normal",
        "prompt_style": "Mantén un tono natural y conversacional. Sé cálido pero profesional.",
    },
}


def get_voice_style(sentiment: str) -> dict:
    """Get voice parameters for a given sentiment label."""
    return SENTIMENT_MAP.get(sentiment, SENTIMENT_MAP["neutral"])


def get_emotional_prompt_extension(sentiment: str, confidence: float = 0.0) -> str:
    """Generate a system prompt extension that adapts the agent's tone."""
    style = get_voice_style(sentiment)
    if confidence < 0.3:
        return ""
    return f"\n\n## Estado emocional del cliente\nEl cliente parece estar en un estado {sentiment}.\n{style['prompt_style']}"


def sentiment_from_state(state_classification: dict) -> str:
    """Extract sentiment label from the pipeline's state classification."""
    if not state_classification:
        return "neutral"
    emotion = state_classification.get("emocion", "")
    if emotion in SENTIMENT_MAP:
        return emotion
    risk = state_classification.get("riesgo", 0)
    urgency = state_classification.get("urgencia", 0)
    tone = state_classification.get("tono", "")
    if risk > 0.5 or urgency > 0.5:
        return "urgent"
    if tone in ("negative", "angry", "sad"):
        return "negative"
    if tone in ("positive", "happy"):
        return "positive"
    return "neutral"
