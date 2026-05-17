from datetime import datetime, timezone
from pydantic import BaseModel, Field

# ─── Scoring Context (structured input for scoring) ────────────────

class ScoringContext(BaseModel):
    state: dict | None = None
    profile_id: str = ""
    impronta_values: dict = Field(default_factory=dict)
    query_embedding: list[float] | None = None
    session_depth: int = 0


# ─── PatternFormat (for N3 generated patterns) ─────────────────────

class PatternFormat(BaseModel):
    context_signature: str = ""
    best_intervention_type: str = ""
    imprint_range: dict = Field(default_factory=dict)
    success_rate: float = 0.0
    sample_size: int = 0
    trigger_conditions: list[str] = Field(default_factory=list)


