from datetime import datetime
from typing import Any, NotRequired, TypedDict

from .profile import Profile
from .impronta import Impronta
from .memory import CaseMemory, RankedCase, PatternMemory, RawMemory, ExecutionMemory
from .client import ClientProfile, Alert


class StateClassification(TypedDict):
    riesgo: float
    emocion: str
    urgencia: float
    intencion: str
    tono: str


class Decision(TypedDict):
    agent: str
    action: str
    reasoning: str
    timestamp: str
    data_snapshot: dict[str, Any]


class Evaluation(TypedDict):
    score: float
    impronta_adherence: float
    factual_consistency: float | None
    safety_check: bool
    feedback: str
    anti_patterns_detected: list[str]


class AgentState(TypedDict):
    session_id: str
    profile_id: str
    user_id: str
    message: str
    context: dict[str, Any]

    profile: NotRequired[Profile]
    impronta: NotRequired[Impronta]
    impronta_rules: NotRequired[list[str]]
    state_classification: NotRequired[StateClassification]
    context_signature: NotRequired[str]

    raw_memories: NotRequired[list[RawMemory]]
    retrieved_cases: NotRequired[list[CaseMemory]]
    ranked_cases: NotRequired[list[RankedCase]]
    patterns: NotRequired[list[PatternMemory]]
    insights: NotRequired[list[dict]]
    knowledge_docs: NotRequired[list[dict]]

    client_profile: NotRequired[ClientProfile]
    client_analysis: NotRequired[dict]
    alerts: NotRequired[list[Alert]]

    prompt: NotRequired[str]
    llm_response: NotRequired[str]
    evaluation: NotRequired[Evaluation]
    validation: NotRequired[dict]

    final_response: NotRequired[str]
    execution: NotRequired[ExecutionMemory]
    confidence: NotRequired[float]
    confidence_details: NotRequired[dict]
    decisions: NotRequired[list[Decision]]

    next_agent: str
    errors: NotRequired[list[str]]
