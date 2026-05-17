from datetime import datetime, timezone
from pydantic import BaseModel, Field

_utcnow = lambda: datetime.now(tz=timezone.utc)
from .impronta import Impronta


# ─── N1: Raw Memory ───────────────────────────────────────────────

class RawMemory(BaseModel):
    id: str = ""
    profile_id: str
    client_id: str = ""  # aislamiento por cliente
    coach_id: str = ""   # F3: aislamiento por coach (multi-tenant)
    content: str
    source_type: str = "unknown"
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: _utcnow())


# ─── N2: Case Memory (Structured Experience) ──────────────────────

class CaseMetadata(BaseModel):
    category: str = "general"
    tags: list[str] = Field(default_factory=list)
    outcome: float | None = None
    feedback_score: float | None = None
    usage_count: int = 0
    source: str = "live"
    llm_model: str = ""
    duration_ms: int = 0
    content_hash: str = ""  # SHA-256 del contexto para deduplicación


class CaseMemory(BaseModel):
    id: str = ""
    profile_id: str
    client_id: str = ""  # ← nuevo
    agent_id: str | None = None

    context: str
    intervention: str
    impronta_applied: Impronta | None = None
    outcome: float | None = None

    state_classification: dict = Field(default_factory=dict)
    knowledge_used: list[str] = Field(default_factory=list)

    metadata: CaseMetadata = Field(default_factory=CaseMetadata)
    created_at: datetime = Field(default_factory=lambda: _utcnow())
    updated_at: datetime = Field(default_factory=lambda: _utcnow())


class ScoredCase(BaseModel):
    case: CaseMemory
    semantic_score: float = 0.0


class RankedCase(BaseModel):
    case: CaseMemory
    semantic_score: float = 0.0
    composite_score: float = 0.0
    scoring_details: dict[str, float] = Field(default_factory=dict)


# ─── N3: Pattern Memory (Insights) ─────────────────────────────────

class PatternMemory(BaseModel):
    id: str = ""
    profile_id: str
    pattern_type: str
    title: str
    description: str
    statistical_signal: float = 0.0
    frequency: int = 0
    impact_score: float = 0.0
    supporting_case_ids: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: _utcnow())
    updated_at: datetime = Field(default_factory=lambda: _utcnow())


# ─── N4: Execution Memory ─────────────────────────────────────────

class ExecutionMemory(BaseModel):
    id: str = ""
    session_id: str
    profile_id: str
    client_id: str = ""  # ← nuevo
    input_text: str
    output_text: str
    impronta_used: Impronta | None = None
    state_classification: dict = Field(default_factory=dict)
    cases_used: list[str] = Field(default_factory=list)
    latency_ms: int = 0
    created_at: datetime = Field(default_factory=lambda: _utcnow())
