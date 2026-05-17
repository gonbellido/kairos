"""Etapa 3: Output adapter — sends responses through the appropriate channel."""

import asyncio
import logging
from kairos.agents.classifier import InputChannel

logger = logging.getLogger(__name__)


async def send_response(
    text: str,
    channel: InputChannel,
    session_id: str,
    metadata: dict | None = None,
    is_enrichment: bool = False,
) -> bool:
    """Send response through the correct channel. Returns True if sent."""
    metadata = metadata or {}
    try:
        match channel:
            case InputChannel.TELEGRAM:
                return await _send_telegram(text, metadata)
            case InputChannel.WHATSAPP:
                return await _send_whatsapp(text, metadata)
            case InputChannel.WEB:
                return await _send_web(text, session_id, is_enrichment)
            case InputChannel.LIVEKIT:
                return await _send_livekit(text, session_id)
    except Exception as e:
        logger.error("Output adapter error [%s]: %s", channel.value, e)
        return False


# ── Telegram ──

async def _send_telegram(text: str, metadata: dict) -> bool:
    chat_id = metadata.get("chat_id")
    if not chat_id:
        return False
    try:
        from kairos.engine.telegram_bot import get_bot
        bot = get_bot()
        if bot:
            await bot.send_message(chat_id=chat_id, text=text[:4000])
            return True
    except Exception:
        pass
    return False


# ── WhatsApp ──

async def _send_whatsapp(text: str, metadata: dict) -> bool:
    # Placeholder: WhatsApp Cloud API integration
    logger.debug("WhatsApp output not configured: %s", text[:50])
    return False


# ── Web (SSE) ──

_web_sessions: dict[str, asyncio.Queue] = {}

async def _send_web(text: str, session_id: str, is_enrichment: bool = False) -> bool:
    queue = _web_sessions.get(session_id)
    if queue:
        await queue.put({"text": text, "is_enrichment": is_enrichment})
        return True
    return False


def register_web_session(session_id: str) -> asyncio.Queue:
    queue = asyncio.Queue()
    _web_sessions[session_id] = queue
    return queue


def unregister_web_session(session_id: str) -> None:
    _web_sessions.pop(session_id, None)


# ── LiveKit ──

async def _send_livekit(text: str, session_id: str) -> bool:
    try:
        from kairos.adapters.livekit_adapter import send_audio
        await send_audio(text=text, room_name=session_id)
        return True
    except Exception:
        pass
    return False
