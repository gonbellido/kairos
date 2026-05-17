"""Etapa 6: Voice path — pure async functions, no LangGraph.

Sequence: filler → sub-classify → LLM response → TTS → deliver → save memory.
"""

import asyncio
import logging
import os
import random

logger = logging.getLogger(__name__)

FILLER_PHRASES = [
    "Entiendo, déjame pensar en eso.",
    "Interesante, dame un momento.",
    "Estoy procesando lo que me dijiste.",
    "Permíteme reflexionar sobre eso.",
    "Escucho, un instante.",
]


async def run(
    message: str,
    session_id: str,
    client_id: str | None = None,
    coach_id: str = "",
    journey_engine=None,
) -> None:
    """Voice path: filler → sub-classify → response → TTS → audio delivery."""

    # 1. Filler immediately — doesn't wait for worker
    filler_task = asyncio.create_task(_send_filler(session_id))

    # 2. Sub-classify the transcribed text
    from kairos.agents.classifier import classify, InputChannel

    expects_data = False
    if journey_engine and client_id:
        try:
            cj = await journey_engine.get_client_journey(client_id)
            if cj and cj.get("journey"):
                phase = cj.get("current_phase_id", "")
                expects_data = bool(phase)  # intake phase expects structured data
        except Exception:
            pass

    text_cls = classify(
        message=message,
        channel=InputChannel.WEB,
        journey_phase_expects_data=expects_data,
    )

    # 3. Generate response (with or without RAG)
    if text_cls.needs_rag:
        from kairos.memory.memory import get_across_sessions
        context = await get_across_sessions(client_id or "", message, limit=5)
        response = await _worker_with_context(message, context, client_id, journey_engine)
    else:
        from kairos.paths.fast_path import run as fast_run
        response = await fast_run(
            message=message, session_id=session_id,
            client_id=client_id, coach_id=coach_id,
            journey_engine=journey_engine, classifier_result=text_cls,
        )

    # 4. TTS + deliver audio
    from kairos.adapters.livekit_adapter import send_audio, interrupt_filler
    await interrupt_filler(session_id)
    await send_audio(text=response, room_name=session_id)

    # 5. Cancel filler if still running
    filler_task.cancel()
    try:
        await filler_task
    except asyncio.CancelledError:
        pass

    # 6. Save memory async
    from kairos.memory.memory import append_raw
    asyncio.create_task(append_raw(session_id, client_id or "", "user", message))
    asyncio.create_task(append_raw(session_id, client_id or "", "assistant", response))


async def _send_filler(session_id: str) -> None:
    phrase = random.choice(FILLER_PHRASES)
    try:
        from kairos.adapters.livekit_adapter import send_audio
        await send_audio(text=phrase, room_name=session_id, is_filler=True)
    except Exception:
        pass


async def _worker_with_context(
    message: str, context: list[dict], client_id: str | None, journey_engine
) -> str:
    import openai

    system = "Eres un coach profesional. Usa el contexto previo para dar una respuesta informada y empática."
    if context:
        ctx_text = "\n".join(
            f"{h.get('role','?')}: {h.get('content','')[:200]}" for h in context[:5]
        )
        system += f"\n\n## Historial relevante\n{ctx_text}"

    c = openai.AsyncOpenAI(
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=os.getenv("OPENAI_BASE_URL", ""),
    )
    r = await c.chat.completions.create(
        model=os.getenv("LLM_MODEL", "deepseek-chat"),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": message}],
        max_tokens=1024,
    )
    return r.choices[0].message.content or ""
