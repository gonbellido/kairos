from datetime import datetime, timezone
from pydantic import BaseModel, Field

_utcnow = lambda: datetime.now(tz=timezone.utc)
from .impronta import Impronta, ImprontaConstraints


class Profile(BaseModel):
    id: str
    name: str
    description: str
    version: str = "0.1.0"
    active: bool = True

    system_prompt_template: str

    default_impronta: Impronta
    impronta_constraints: ImprontaConstraints | None = None

    scoring_weights: dict[str, float] = Field(default_factory=lambda: {
        "semantic": 0.35,
        "recency": 0.25,
        "outcome": 0.25,
        "frequency": 0.15,
    })

    plugins: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: _utcnow())
    updated_at: datetime = Field(default_factory=lambda: _utcnow())
