"""Etapa 2 v2: Deterministic message classifier — no LLM calls, <50ms."""

from dataclasses import dataclass
from enum import Enum


class MessagePath(Enum):
    FAST = "fast"
    DEEP = "deep"
    VOICE = "voice"


class InputChannel(Enum):
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    WEB = "web"
    LIVEKIT = "livekit"


@dataclass
class ClassifierResult:
    path: MessagePath
    channel: InputChannel
    complexity_score: float = 0.0
    detected_intent: str = "greeting"
    needs_rag: bool = False
    needs_memory: bool = False
    risk_level: str = "low"


MEMORY_TRIGGERS_EN = [
    'said', 'told me', 'before', 'remember', 'commented',
    'spoke', 'mentioned', 'last time', 'last week',
    'yesterday', 'the last time', 'latest',
]

MEMORY_TRIGGERS = [
    "dijiste", "te dije", "antes", "recuerdas", "comenté", "comente",
    "hablamos", "mencioné", "mencione", "la vez anterior", "la semana",
    "ayer", "la última vez", "última", "ultimo",
]

DEEP_TRIGGERS_EN = [
    'explain', 'do not understand', 'help me',
    'feel like', 'it happens to me', 'have a problem', 'need',
    'what does it mean', 'why', 'how can I', 'analysis',
    'pattern', 'blockage', 'fear', 'anxiety', 'crisis',
    'emotion', 'process', 'work', 'deepen',
]

DEEP_TRIGGERS = [
    "explícame", "explicame", "no entiendo", "ayúdame", "ayudame",
    "siento que", "me pasa que", "tengo un problema", "necesito",
    "qué significa", "por qué", "cómo puedo", "análisis", "analisis",
    "patrón", "patron", "bloqueo", "miedo", "ansiedad", "crisis",
    "emoción", "emocion", "proceso", "trabajar", "profundizar",
]

QUESTION_STARTS_EN = (
    'what', 'how', 'when', 'where', 'why', 'who', 'which',
)

QUESTION_STARTS = (
    "qué", "cómo", "cuándo", "dónde", "por qué", "quién", "cuál",
    "que", "como", "cuando", "donde", "quien", "cual",
)

HIGH_RISK = ["suicidio", "hacerme daño", "no quiero vivir", "colapso"]
MED_RISK = ["no puedo más", "estoy mal", "llorar", "angustia", "pánico"]


def classify(
    message: str,
    channel: InputChannel = InputChannel.WEB,
    journey_phase_expects_data: bool = False,
) -> ClassifierResult:

    # 1. LiveKit → VOICE
    if channel == InputChannel.LIVEKIT:
        return ClassifierResult(
            path=MessagePath.VOICE, channel=channel,
            complexity_score=0.5, detected_intent="voice",
            risk_level=detect_risk(message),
        )

    text = message.strip()
    words = text.split()
    has_question = "?" in text or text.lower().startswith(QUESTION_STARTS + QUESTION_STARTS_EN)
    msg_lower = text.lower()

    # 2. DEEP triggers → always DEEP
    if any(t in msg_lower for t in DEEP_TRIGGERS + DEEP_TRIGGERS_EN):
        return ClassifierResult(
            path=MessagePath.DEEP, channel=channel,
            complexity_score=0.8, detected_intent="clinical",
            needs_rag=True, needs_memory=True,
            risk_level=detect_risk(text),
        )

    # 3. Journey expects data → FAST (check before word count)
    if journey_phase_expects_data:
        return ClassifierResult(
            path=MessagePath.FAST, channel=channel,
            complexity_score=0.2, detected_intent="journey_data",
            risk_level=detect_risk(text),
        )

    # 4. Memory triggers → FAST with needs_memory
    if any(t in msg_lower for t in MEMORY_TRIGGERS + MEMORY_TRIGGERS_EN):
        return ClassifierResult(
            path=MessagePath.FAST, channel=channel,
            complexity_score=0.4, detected_intent="question",
            needs_memory=True,
            risk_level=detect_risk(text),
        )

    # 5. Short, no question → FAST
    if len(words) <= 5 and not has_question:
        return ClassifierResult(
            path=MessagePath.FAST, channel=channel,
            complexity_score=0.1, detected_intent="greeting",
            risk_level=detect_risk(text),
        )

    # 6. Simple question → FAST
    if has_question and len(words) <= 10:
        return ClassifierResult(
            path=MessagePath.FAST, channel=channel,
            complexity_score=0.3, detected_intent="question",
            risk_level=detect_risk(text),
        )

    # 7. Default → DEEP
    return ClassifierResult(
        path=MessagePath.DEEP, channel=channel,
        complexity_score=0.7, detected_intent="question",
        needs_rag=True, needs_memory=True,
        risk_level=detect_risk(text),
    )


def detect_risk(message: str) -> str:
    msg = message.lower()
    if any(k in msg for k in HIGH_RISK):
        return "high"
    if any(k in msg for k in MED_RISK):
        return "medium"
    return "low"
