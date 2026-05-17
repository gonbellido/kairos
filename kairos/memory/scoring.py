import math
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
from kairos.core.memory import ScoredCase, RankedCase
from kairos.core.scoring_context import ScoringContext


@dataclass
class ScoringWeights:
    relevance: float = 0.35
    recency: float = 0.25
    outcome: float = 0.25
    frequency: float = 0.15

    @classmethod
    def from_dict(cls, d: dict) -> "ScoringWeights":
        return cls(
            relevance=float(d.get("relevance", d.get("semantic", 0.35))),
            recency=float(d.get("recency", 0.25)),
            outcome=float(d.get("outcome", 0.25)),
            frequency=float(d.get("frequency", 0.15)),
        )


class Scorer(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def weight(self) -> float: ...

    @abstractmethod
    async def score(self, case: ScoredCase, ctx: ScoringContext) -> float: ...


class SemanticScorer(Scorer):
    def __init__(self, weight: float = 0.35):
        self._weight = weight
    @property
    def name(self) -> str: return "semantic"
    @property
    def weight(self) -> float: return self._weight
    async def score(self, case: ScoredCase, ctx: ScoringContext) -> float:
        return case.semantic_score


class RecencyScorer(Scorer):
    def __init__(self, weight: float = 0.25, decay: float = 0.05):
        self._weight = weight; self._decay = decay
    @property
    def name(self) -> str: return "recency"
    @property
    def weight(self) -> float: return self._weight
    async def score(self, case: ScoredCase, ctx: ScoringContext) -> float:
        days = (_utcnow() - case.case.created_at).days
        return math.exp(-self._decay * days)


class OutcomeScorer(Scorer):
    def __init__(self, weight: float = 0.25):
        self._weight = weight
    @property
    def name(self) -> str: return "outcome"
    @property
    def weight(self) -> float: return self._weight
    async def score(self, case: ScoredCase, ctx: ScoringContext) -> float:
        outcome, fb = case.case.outcome, case.case.metadata.feedback_score
        if outcome is not None and fb is not None:
            return (outcome * 0.6 + fb * 0.4) * 0.5 + 0.5
        if outcome is not None:
            return outcome * 0.5 + 0.5
        if fb is not None:
            return fb * 0.5 + 0.5
        return 0.5


class FrequencyScorer(Scorer):
    def __init__(self, weight: float = 0.15, max_usage: int = 10):
        self._weight = weight; self._max = max_usage
    @property
    def name(self) -> str: return "frequency"
    @property
    def weight(self) -> float: return self._weight
    async def score(self, case: ScoredCase, ctx: ScoringContext) -> float:
        usage = case.case.metadata.usage_count
        return max(0.0, 1.0 - usage / self._max)


class ContextualScorer(Scorer):
    """Scores higher when state classification matches case context."""
    def __init__(self, weight: float = 0.1):
        self._weight = weight
    @property
    def name(self) -> str: return "contextual"
    @property
    def weight(self) -> float: return self._weight
    async def score(self, case: ScoredCase, ctx: ScoringContext) -> float:
        if not ctx.state:
            return 0.5
        state_emo = ctx.state.get("emocion", "")
        case_state = case.case.state_classification or {}
        case_emo = case_state.get("emocion", "")
        if state_emo and case_emo and state_emo == case_emo:
            return 0.9
        return 0.5


class ClientSimilarityScorer(Scorer):
    """Scores higher when case context is similar to this client's profile."""
    def __init__(self, weight: float = 0.15):
        self._weight = weight
    @property
    def name(self) -> str: return "client_similarity"
    @property
    def weight(self) -> float: return self._weight
    async def score(self, case: ScoredCase, ctx: ScoringContext) -> float:
        if not ctx.state:
            return 0.5
        estado = ctx.state
        case_state = case.case.state_classification or {}
        matches = 0
        total = 0
        for key in ("emocion", "intencion", "tono"):
            sv = estado.get(key)
            cv = case_state.get(key)
            if sv and cv:
                total += 1
                if sv == cv:
                    matches += 1
        if total == 0:
            return 0.5
        return 0.5 + 0.5 * (matches / total)


class ScoringEngine:
    def __init__(self, weights: ScoringWeights | None = None):
        self._weights = weights or ScoringWeights()

    async def score(
        self,
        cases: list[ScoredCase],
        scoring_ctx: ScoringContext | None = None,
    ) -> list[RankedCase]:
        ctx = scoring_ctx or ScoringContext()
        scorers: list[Scorer] = [
            SemanticScorer(self._weights.relevance),
            RecencyScorer(self._weights.recency),
            OutcomeScorer(self._weights.outcome),
            FrequencyScorer(self._weights.frequency),
            ContextualScorer(0.1),
            ClientSimilarityScorer(0.15),
        ]
        total_weight = sum(s.weight for s in scorers)
        ranked = []
        for sc in cases:
            composite = 0.0
            details = {}
            for s in scorers:
                score = await s.score(sc, ctx)
                composite += score * s.weight
                details[s.name] = score
            # Normalizar para que composite_score esté en [0, 1]
            if total_weight > 0:
                composite = composite / total_weight
            ranked.append(RankedCase(
                case=sc.case,
                semantic_score=sc.semantic_score,
                composite_score=composite,
                scoring_details=details,
            ))
        ranked.sort(key=lambda r: r.composite_score, reverse=True)
        return ranked

    def select_top(self, ranked: list[RankedCase], max_count: int = 5) -> list[RankedCase]:
        return ranked[:max_count]
