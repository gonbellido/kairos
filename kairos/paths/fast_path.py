"""Etapa 4: Fast path — LLM self-reports collected data via DATA:{...} tag."""

import asyncio
import json
import logging
import os
import re

logger = logging.getLogger(__name__)


async def run(
    message: str,
    session_id: str,
    client_id: str | None = None,
    coach_id: str = "",
    journey_engine=None,
    classifier_result=None,
    needs_memory: bool = False,
    memory_hits: list = None,
) -> str:
    """Fast path with LLM-driven data collection via DATA:{} tag."""

    prompt = ""
    collected = {}
    collects_fields = []

    if journey_engine and client_id:
        try:
            cj = await journey_engine.get_client_journey(client_id)
            if cj and cj.get("journey"):
                journey = cj.get("journey", {})
                agents = journey.get("agents", [])
                agent_data = next(
                    (a for a in agents if a["id"] == cj.get("current_agent_id")),
                    agents[0] if agents else None,
                )
                cf = agent_data.get("collects_fields", []) if agent_data else []
                if isinstance(cf, str):
                    cf = json.loads(cf)
                collects_fields = cf if isinstance(cf, list) else []

                collected = cj.get("collected_data", {}) or {}
                if isinstance(collected, str):
                    collected = json.loads(collected)

                # Build prompt: agent context + standard JSON format wrapper
                prompt = await journey_engine.compose_agent_prompt(
                    client_id, message, memory_hits=memory_hits or []
                )
                if collects_fields:
                    missing = [f for f in collects_fields if f not in collected or not collected[f]]
                    allowed_tags = agent_data.get("allowed_tags", []) if agent_data else []
                    prompt += _build_format_instruction(missing, allowed_tags)

        except Exception as e:
            logger.warning("Fast path: journey setup skipped: %s", e)

    if not prompt:
        prompt = "Eres un coach profesional. Responde con empatía y claridad."

    # Conversation history
    if needs_memory and client_id:
        try:
            from kairos.memory.memory import get_recent
            history = await get_recent(session_id, limit=5)
            if history:
                history_text = "\n".join(
                    f"{'Cliente' if h.get('role') == 'user' else 'Agente'}: {h.get('content', '')[:200]}"
                    for h in history
                )
                prompt += f"\n\n## Conversación reciente\n{history_text}"
        except Exception:
            pass

    # Single LLM call — force JSON for intake data collection
    use_json = bool(collects_fields)
    response_text = await _call_llm(prompt, message, use_json)

    # Extract collected data from JSON response
    new_data = _extract_data(response_text)
    if new_data and journey_engine and client_id:
        collected.update(new_data)
        await _update_collected(journey_engine, client_id, collected)

    # Clean up: extract message text, strip DATA tags
    response_text = _clean_response(response_text)

    # Check if enough data collected → advance (5+ is enough)
    if journey_engine and client_id and collects_fields and collected:
        data_count = len([v for k, v in collected.items() if v and not k.startswith("_")])
        threshold = min(len(collects_fields), 5)
        logger.info("fast_path advance check: %d/%d fields (need %d)", data_count, len(collects_fields), threshold)
        if data_count >= threshold:
            try:
                await journey_engine.advance_client(client_id)
                logger.info("Journey phase completed: %d fields → ADVANCED", data_count)
            except Exception as e:
                logger.warning("Journey advance failed: %s", e)
        else:
            logger.info("fast_path: not enough data yet (%d < %d)", data_count, threshold)

    # Save raw memory async
    asyncio.create_task(_save_raw(session_id, client_id, message, response_text))

    return response_text


# ── Helpers ──

def _build_format_instruction(missing: list, allowed_tags: list) -> str:
    """Standard JSON format wrapper appended to every intake-phase prompt."""
    parts = [
        '\n\n## Formato de respuesta (obligatorio)',
        'Responde ÚNICAMENTE con JSON válido:',
        '{"message": "texto al cliente", "collected_data": {"campo": "valor"}, "suggested_tags": [], "phase_completed": false}',
        '- "message": lo que el cliente lee, en lenguaje natural y empático',
        '- "collected_data": SOLO campos NUEVOS recolectados en ESTE turno (no repitas los ya obtenidos)',
        '- "suggested_tags": lista de tags cuando completes todos los campos requeridos',
        '- "phase_completed": true únicamente cuando la fase esté completamente terminada',
    ]
    if missing:
        parts.append(f'Campos aún pendientes: {missing}')
        parts.append('Pregunta por UN campo a la vez. NO repitas lo ya recolectado.')
    else:
        parts.append('Todos los campos recolectados. Indica que la fase está completa.')
        if allowed_tags:
            parts.append(f'Usa suggested_tags: {allowed_tags}')
    return '\n'.join(parts)


def _extract_data(response: str) -> dict:
    """Extract collected data from JSON response (handles code blocks)."""
    raw = response.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
    try:
        data = json.loads(raw.strip())
        if isinstance(data, dict):
            # Check for collected_data or structured
            collected = data.get("collected_data", data.get("structured", {}))
            if isinstance(collected, dict) and collected:
                return {k: v for k, v in collected.items() if v and not k.startswith("_")}
    except (json.JSONDecodeError, ValueError):
        pass
    return {}


def _clean_response(response: str) -> str:
    """Extract message text from JSON or markdown code blocks."""
    raw = response.strip()
    # Remove markdown code fences
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
    # JSON format
    try:
        data = json.loads(raw.strip())
        if isinstance(data, dict) and "message" in data:
            return data["message"]
    except (json.JSONDecodeError, ValueError):
        pass
    return raw.strip()


async def _update_collected(journey_engine, client_id: str, collected: dict) -> None:
    try:
        await journey_engine.save_collected(client_id, collected)
    except Exception as e:
        # Fallback: direct DB update if save_collected not available
        try:
            from kairos.db.models import ClientJourneyModel
            from sqlalchemy import update
            sf = journey_engine._sf
            async with sf() as s:
                await s.execute(
                    update(ClientJourneyModel)
                    .where(ClientJourneyModel.client_id == client_id)
                    .values(collected_data=collected)
                )
                await s.commit()
        except Exception as e2:
            logger.warning("Failed to update collected_data: %s / %s", e, e2)


async def _call_llm(system_prompt: str, user_message: str, force_json: bool = False) -> str:
    import openai
    settings = _get_settings()
    client = openai.AsyncOpenAI(
        api_key=settings.get("llm_api_key", ""),
        base_url=settings.get("llm_base_url", ""),
    )
    kwargs = {
        "model": settings.get("llm_model", "deepseek-chat"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": float(settings.get("llm_temperature", 0.7)),
        "max_tokens": int(settings.get("llm_max_tokens", 2048)),
    }
    if force_json:
        kwargs["response_format"] = {"type": "json_object"}
    resp = await client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


async def _save_raw(session_id: str, client_id: str | None, user_msg: str, agent_msg: str) -> None:
    try:
        from kairos.memory.memory import append_raw
        await asyncio.gather(
            append_raw(session_id, client_id or "", "user", user_msg),
            append_raw(session_id, client_id or "", "assistant", agent_msg),
        )
    except Exception:
        pass


def _get_settings() -> dict:
    return {
        "llm_api_key": os.getenv("LLM_API_KEY", ""),
        "llm_base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "llm_model": os.getenv("LLM_MODEL", "deepseek-chat"),
        "llm_temperature": os.getenv("LLM_TEMPERATURE", "0.7"),
        "llm_max_tokens": os.getenv("LLM_MAX_TOKENS", "2048"),
    }
