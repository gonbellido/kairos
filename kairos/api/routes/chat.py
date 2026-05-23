"""Chat endpoints — v2 with classifier-driven routing."""

import json
import logging
from fastapi import APIRouter, Request, HTTPException

from kairos.api.schemas import ChatRequest, ChatResponse
from kairos.agents.classifier import classify, InputChannel, MessagePath

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: Request, body: ChatRequest):
    runtime = req.app.state.runtime
    try:
        result = await runtime.run(
            session_id=body.session_id,
            profile_id=body.profile_id,
            message=body.message,
            user_id=body.user_id,
            context=body.context,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return ChatResponse(
        session_id=body.session_id,
        response=result.get("final_response", ""),
        confidence=result.get("confidence", 0.0),
        profile_id=body.profile_id,
        classification=dict(result.get("state_classification", {})),
    )


@router.post("/chat/sync")
async def chat_sync_endpoint(req: Request, body: ChatRequest):
    """Synchronous endpoint — uses fast_path when possible."""
    client_id = body.context.get("client_id", "")
    coach_id = body.context.get("coach_id", body.user_id or "")
    je = getattr(req.app.state, "journey_engine", None)

    # Classify to decide path
    expects_data = False
    if je and client_id:
        try:
            cj = await je.get_client_journey(client_id)
            if cj and cj.get("journey"):
                expects_data = True  # journey intake expects structured answers
        except Exception:
            pass

    result = classify(body.message, channel=InputChannel.WEB, journey_phase_expects_data=expects_data)

    if result.path == MessagePath.FAST:
        return await _handle_fast(req, body, client_id, coach_id, je, result)

    # DEEP: use original orchestrator for now
    return await _handle_legacy(req, body, client_id, je)


async def _handle_fast(req, body, client_id, coach_id, je, result):
    """Fast path: 1 LLM call, no Qdrant semantic, PostgreSQL for journey."""
    from kairos.paths.fast_path import run as fast_run

    response_text = await fast_run(
        message=body.message,
        session_id=body.session_id,
        client_id=client_id,
        coach_id=coach_id,
        journey_engine=je,
        classifier_result=result,
        needs_memory=result.needs_memory,
    )

    # Extract message from JSON if present
    extracted = _extract_message(response_text)

    return {"response": extracted, "confidence": 0.9}


async def _handle_legacy(req, body, client_id, je):
    """Legacy path: full orchestrator + journey injection."""
    runtime = req.app.state.runtime

    # Inject journey prompt
    if client_id and je:
        try:
            cj = await je.get_client_journey(client_id)
            if cj and cj.get("journey"):
                journey_prompt = await je.compose_agent_prompt(client_id, body.message)
                if journey_prompt:
                    body.context["_journey_system_prompt"] = journey_prompt
        except Exception as e:
            logger.warning("Journey prompt skipped: %s", e)

    try:
        result = await runtime.run(
            session_id=body.session_id,
            profile_id=body.profile_id,
            message=body.message,
            user_id=body.user_id,
            context=body.context,
        )
        response_text = result.get("final_response", "")

        # Validate and advance journey
        if client_id and je:
            try:
                cj = await je.get_client_journey(client_id)
                if cj and cj.get("journey"):
                    agents = cj["journey"].get("agents", [])
                    agent_data = next((a for a in agents if a["id"] == cj.get("current_agent_id")), None)
                    va = await je.validate_and_advance(client_id, response_text, agent_data)
                    if va.get("message") and va["message"] != response_text:
                        response_text = va["message"]
            except Exception as e:
                logger.warning("Journey advance skipped: %s", e)

        return {"response": _extract_message(response_text), "confidence": result.get("confidence", 0.0)}

    except Exception as e:
        return {"response": "", "error": str(e)}


def _extract_message(text: str) -> str:
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            if "message" in data:
                return data["message"]
            # Fallback: use first non-empty field value as the message
            for v in data.values():
                if isinstance(v, str) and v.strip():
                    return v.strip()
    except Exception:
        pass
    return text
