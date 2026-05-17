"""Etapa 9: Main orchestrator — ties classifier, paths, and output adapter together."""

import asyncio
import logging

from kairos.agents.classifier import (
    classify, ClassifierResult, MessagePath, InputChannel,
)
from kairos.adapters.input_adapter import adapt_input, NormalizedInput
from kairos.adapters.output_adapter import send_response

logger = logging.getLogger(__name__)


async def run(
    payload: dict,
    channel: InputChannel,
    journey_engine=None,
) -> str:
    """Main entry point. Classifies → routes to path → sends response."""

    # 1. Adapt input
    normalized = await adapt_input(payload, channel)

    # 2. Classify
    expects_data = False
    if journey_engine and normalized.client_id:
        try:
            cj = await journey_engine.get_client_journey(normalized.client_id)
            if cj and cj.get("journey"):
                expects_data = bool(cj.get("current_phase_id"))
        except Exception:
            pass

    result = classify(
        message=normalized.raw_text,
        channel=channel,
        journey_phase_expects_data=expects_data,
    )

    # 3. Route to appropriate path
    response = ""
    match result.path:
        case MessagePath.FAST:
            from kairos.paths.fast_path import run as fast_run
            response = await fast_run(
                message=normalized.raw_text,
                session_id=normalized.session_id,
                client_id=normalized.client_id,
                coach_id=normalized.coach_id,
                journey_engine=journey_engine,
                classifier_result=result,
                needs_memory=result.needs_memory,
            )
            await send_response(
                text=response,
                channel=channel,
                session_id=normalized.session_id,
                metadata=normalized.metadata,
            )

        case MessagePath.DEEP:
            from kairos.paths.fast_path import run as fast_run
            from kairos.paths.deep_path import run as deep_run

            # Fast first → immediate response
            response = await fast_run(
                message=normalized.raw_text,
                session_id=normalized.session_id,
                client_id=normalized.client_id,
                coach_id=normalized.coach_id,
                journey_engine=journey_engine,
                classifier_result=result,
                needs_memory=result.needs_memory,
            )
            await send_response(
                text=response,
                channel=channel,
                session_id=normalized.session_id,
                metadata=normalized.metadata,
            )
            # Deep in background → enrich_worker sends enrichment later
            asyncio.create_task(
                deep_run(
                    message=normalized.raw_text,
                    session_id=normalized.session_id,
                    client_id=normalized.client_id,
                    coach_id=normalized.coach_id,
                    journey_id=normalized.journey_id,
                    channel=channel.value,
                    metadata=normalized.metadata,
                    fast_response=response,
                    risk_level=result.risk_level,
                )
            )

        case MessagePath.VOICE:
            from kairos.paths.voice_path import run as voice_run
            await voice_run(
                message=normalized.raw_text,
                session_id=normalized.session_id,
                client_id=normalized.client_id,
                coach_id=normalized.coach_id,
                journey_engine=journey_engine,
            )

    return response
