"""Stream endpoint — SSE with classifier-driven routing."""

import json
import logging
from typing import AsyncGenerator
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from kairos.agents.classifier import classify, InputChannel, MessagePath
from kairos.engine.activity import log_activity

logger = logging.getLogger(__name__)
router = APIRouter()


class StreamRequest(BaseModel):
    session_id: str = "default"
    profile_id: str
    message: str
    user_id: str = "default"
    context: dict = {}


@router.post("/chat/stream")
async def chat_stream(req: Request, body: StreamRequest):
    runtime = req.app.state.runtime
    client_id = body.context.get("client_id", "")
    je = getattr(req.app.state, "journey_engine", None)
    expects_data = False

    # Journey: auto-assign + inject prompt
    memory_hits = []
    if client_id and je:
        try:
            cj = await je.get_client_journey(client_id)
            if not cj:
                coach_db = req.app.state.coach_db
                coach_info = await coach_db.get_by_id(body.user_id)
                coach_default_id = coach_info.get("default_journey_id", "") if coach_info else ""

                # Search both default journeys AND coach's own journeys
                default_j = await je.list_journeys("default", full=False)
                coach_j = await je.list_journeys(body.user_id, full=False) if body.user_id != "default" else []
                all_journeys = default_j + [j for j in coach_j if j["id"] not in {x["id"] for x in default_j}]

                coaching = next((j for j in all_journeys if j["id"] == coach_default_id), None)
                if not coaching:
                    coaching = next((j for j in all_journeys if j.get("profile_type") == "coaching"),
                                    all_journeys[0] if all_journeys else None)
                if coaching:
                    await je.assign_client(client_id, body.user_id, coaching["id"])
                    cj = await je.get_client_journey(client_id)
                    log_activity("journey_assigned", {"client_id": client_id, "journey": coaching["name"]})
            if cj and cj.get("journey"):
                # RAG: search coach knowledge base + client session history
                try:
                    raw_store = req.app.state.runtime.raw_store
                    coach_id_rag = body.context.get("coach_id", body.user_id or "")
                    if hasattr(raw_store, "search_relevant"):
                        coach_hits = await raw_store.search_relevant(
                            query_text=body.message, profile_id="coaching",
                            client_id="", coach_id=coach_id_rag, top_k=3
                        )
                        client_hits = await raw_store.search_relevant(
                            query_text=body.message, profile_id="coaching",
                            client_id=client_id, coach_id=coach_id_rag, top_k=2
                        )
                        # Only include hits above relevance threshold (score > 0.5)
                        memory_hits = (
                            [{"source": "coach_kb", "content": h.get("content", "")}
                             for h in coach_hits if h.get("_score", 0) > 0.5 and h.get("content")] +
                            [{"source": "session_history", "content": h.get("content", "")}
                             for h in client_hits if h.get("_score", 0) > 0.5 and h.get("content")]
                        )
                except Exception as rag_err:
                    logger.debug("RAG search skipped: %s", rag_err)

                journey_prompt = await je.compose_agent_prompt(
                    client_id, body.message, memory_hits=memory_hits
                )
                if journey_prompt:
                    body.context["_journey_system_prompt"] = journey_prompt
                expects_data = True
        except Exception as e:
            log_activity("journey_error", {"client_id": client_id, "error": str(e)[:100]})

    # Classify
    result = classify(body.message, channel=InputChannel.WEB, journey_phase_expects_data=expects_data)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            log_activity("chat_message", {"client_id": body.user_id, "message": body.message[:100]})

            adv_info = None
            if result.path == MessagePath.FAST:
                response, confidence, adv_info = await _fast_stream(req, body, client_id, je, result, memory_hits)
            else:
                raw_result = await runtime.run(
                    session_id=body.session_id,
                    profile_id=body.profile_id,
                    message=body.message,
                    user_id=body.user_id,
                    context={**body.context, "locale": body.context.get("locale") or getattr(req.state, "lang", "es")},
                )
                response = raw_result.get("final_response", "")
                confidence = raw_result.get("confidence", 0.0)
                if raw_result.get("journey_advanced"):
                    adv_info = raw_result.get("journey_advance_info")

            log_activity("agent_response", {"client_id": body.user_id, "length": len(response), "confidence": confidence})

            if adv_info:
                yield f"data: {json.dumps({'type': 'journey_advance', **adv_info})}\n\n"

            # Emit tokens word by word
            words = response.split(" ")
            for i, word in enumerate(words):
                token = word + (" " if i < len(words) - 1 else "")
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            yield f"data: {json.dumps({'type': 'meta', 'confidence': confidence})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error("Stream error: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _fast_stream(req, body, client_id, je, result, memory_hits=None):
    from kairos.paths.fast_path import run as fast_run
    coach_id = body.context.get("coach_id", body.user_id or "")

    response = await fast_run(
        message=body.message,
        session_id=body.session_id,
        client_id=client_id,
        coach_id=coach_id,
        journey_engine=je,
        classifier_result=result,
        needs_memory=result.needs_memory,
        memory_hits=memory_hits or [],
    )

    # Extract message from JSON
    try:
        data = json.loads(response)
        if isinstance(data, dict) and "message" in data:
            response = data["message"]
    except Exception:
        pass

    # Journey advance
    adv_info = None
    if client_id and je:
        try:
            cj = await je.get_client_journey(client_id)
            if cj and cj.get("journey"):
                old_agent = cj.get("current_agent_id")
                agents = cj["journey"].get("agents", [])
                agent_data = next((a for a in agents if a["id"] == old_agent), None)
                va = await je.validate_and_advance(client_id, response, agent_data)
                if va.get("message") and va["message"] != response:
                    response = va["message"]
                if va.get("advanced") or va.get("phase_completed"):
                    new_cj = await je.get_client_journey(client_id)
                    adv_info = {
                        "from_agent": old_agent,
                        "to_agent": new_cj.get("current_agent_id"),
                        "phase": new_cj.get("current_phase_id")
                    }
        except Exception:
            pass

    return response, 0.9, adv_info
