"""Etapa 3: Input adapter — normalizes messages from 4 channels into one structure."""

from dataclasses import dataclass, field
from kairos.agents.classifier import InputChannel


@dataclass
class NormalizedInput:
    raw_text: str
    channel: InputChannel
    session_id: str
    client_id: str | None = None
    coach_id: str = ""
    journey_id: str | None = None
    audio_data: bytes | None = None
    metadata: dict = field(default_factory=dict)


async def adapt_input(payload: dict, channel: InputChannel) -> NormalizedInput:
    """Normalize input from any channel into a single structure."""
    match channel:
        case InputChannel.TELEGRAM:
            return _adapt_telegram(payload)
        case InputChannel.WHATSAPP:
            return await _adapt_whatsapp(payload)
        case InputChannel.WEB:
            return _adapt_web(payload)
        case InputChannel.LIVEKIT:
            return await _adapt_livekit(payload)


def _adapt_telegram(payload: dict) -> NormalizedInput:
    msg = payload.get("message", {})
    chat = msg.get("chat", {})
    user = msg.get("from", {})
    return NormalizedInput(
        raw_text=msg.get("text", ""),
        channel=InputChannel.TELEGRAM,
        session_id=str(chat.get("id", "")),
        client_id=str(user.get("id", "")) or None,
        metadata={"chat_id": chat.get("id"), "user_id": user.get("id")},
    )


async def _adapt_whatsapp(payload: dict) -> NormalizedInput:
    try:
        entry = payload.get("entry", [{}])[0]
        change = entry.get("changes", [{}])[0]
        value = change.get("value", {})
        msgs = value.get("messages", [{}])
        msg = msgs[0] if msgs else {}
        return NormalizedInput(
            raw_text=msg.get("text", {}).get("body", ""),
            channel=InputChannel.WHATSAPP,
            session_id=msg.get("from", ""),
            client_id=value.get("contacts", [{}])[0].get("wa_id") if value.get("contacts") else None,
            metadata={"phone_id": value.get("metadata", {}).get("phone_number_id", "")},
        )
    except (IndexError, KeyError, AttributeError):
        return NormalizedInput(
            raw_text="", channel=InputChannel.WHATSAPP, session_id="unknown",
        )


def _adapt_web(payload: dict) -> NormalizedInput:
    ctx = payload.get("context", {}) or {}
    return NormalizedInput(
        raw_text=payload.get("message", ""),
        channel=InputChannel.WEB,
        session_id=payload.get("session_id", ""),
        client_id=ctx.get("client_id") or payload.get("user_id"),
        coach_id=ctx.get("coach_id", payload.get("user_id", "")),
        journey_id=ctx.get("journey_id"),
    )


async def _adapt_livekit(payload: dict) -> NormalizedInput:
    audio = payload.get("audio", b"")
    text = ""
    if audio:
        text = await transcribe_audio(audio)
    return NormalizedInput(
        raw_text=text,
        channel=InputChannel.LIVEKIT,
        session_id=payload.get("room_name", ""),
        client_id=payload.get("client_id"),
        audio_data=audio,
    )


async def transcribe_audio(audio: bytes) -> str:
    """STT with Gemini Audio. Returns empty string on failure."""
    try:
        import os
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY", ""))
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = await model.generate_content_async([
            "Transcribe este audio a texto. Responde SOLO con la transcripción.",
            {"mime_type": "audio/webm", "data": audio},
        ])
        return response.text.strip()
    except Exception:
        return ""
