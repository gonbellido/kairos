from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = "default"
    profile_id: str
    message: str
    user_id: str = "default"
    context: dict = Field(default_factory=dict)


class ChatResponse(BaseModel):
    session_id: str
    response: str
    confidence: float
    profile_id: str
    classification: dict = Field(default_factory=dict)


class CaseCreateRequest(BaseModel):
    profile_id: str
    context: str
    intervention: str
    outcome: float | None = None
    category: str = "general"
    tags: list[str] = Field(default_factory=list)
    source: str = "api"
