import logging
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    case_id: str
    score: float  # -1 to 1
    comment: str | None = None


class FeedbackResponse(BaseModel):
    case_id: str
    old_score: float | None
    new_score: float
    re_scored_count: int


@router.post("/", response_model=FeedbackResponse)
async def submit_feedback(req: Request, body: FeedbackRequest):
    runtime = req.app.state.runtime
    try:
        result = await runtime.feedback_processor.ingest_feedback(
            case_id=body.case_id,
            score=body.score,
            comment=body.comment,
        )
        return FeedbackResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
