"""Voice Agent — LLM filler while KAIROS processes the journey response."""

import asyncio
import logging
import os
import sys

import httpx
from livekit.agents import (
    Agent, AgentSession, AutoSubscribe, JobContext, WorkerOptions, cli,
    RoomInputOptions, RoomOutputOptions,
)
from livekit.plugins import silero, deepgram, openai, cartesia

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("kairos.voice")

KAIROS_API = os.environ.get("KAIROS_API_URL", "http://app:8000")


async def kairos_respond(client_id: str, message: str) -> str:
    """Get journey-aware response from KAIROS pipeline."""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{KAIROS_API}/api/v1/chat/sync", json={
                "message": message,
                "session_id": f"voice_{client_id}",
                "profile_id": "coaching",
                "user_id": client_id,
                "context": {"client_id": client_id, "channel": "voice"},
            })
            if r.status_code == 200:
                return r.json().get("response", "")
    except Exception as e:
        logger.warning("KAIROS error: %s", e)
    return ""


async def entrypoint(ctx: JobContext):
    client_id = ctx.room.name.replace("client_", "")
    logger.info("Voice session starting for client=%s", client_id)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    cartesia_key = os.environ.get("CARTESIA_API_KEY", "")
    cartesia_voice = os.environ.get("CARTESIA_VOICE_ID",
                                     "694f9389-aac1-45b6-b726-9d9369183238")
    deepgram_key = os.environ.get("DEEPGRAM_API_KEY", "")
    openai_api_key = os.environ.get("LLM_API_KEY", "")
    openai_base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")
    openai_model = os.environ.get("LLM_MODEL", "deepseek-chat")

    stt_kwargs = {"model": "nova-2", "language": "es"}
    if deepgram_key:
        stt_kwargs["api_key"] = deepgram_key

    session = AgentSession(
        stt=deepgram.STT(**stt_kwargs),
        llm=openai.LLM(model=openai_model, base_url=openai_base_url, api_key=openai_api_key),
        tts=cartesia.TTS(model="sonic-2", voice=cartesia_voice, language="es",
                          api_key=cartesia_key) if cartesia_key else None,
        vad=silero.VAD.load(),
    )

    async def handle_user_input(text: str):
        # Get journey-aware response from KAIROS
        response = await kairos_respond(client_id, text)
        if response:
            # Interrupt filler and deliver real response
            await session.say(response, allow_interruptions=True)
            logger.info("KAIROS response delivered")

    @session.on("user_input_transcribed")
    def on_transcript(ev):
        if ev.is_final and ev.transcript.strip():
            text = ev.transcript.strip()
            logger.info("User: %s", text)
            # Fire KAIROS in background — LLM handles filler response automatically
            asyncio.create_task(handle_user_input(text))

    class VoiceFiller(Agent):
        def __init__(self):
            super().__init__(instructions=(
                "Eres un asistente de coaching de voz de KAIROS, cálido y empático. "
                "Ayudas a clientes con crecimiento personal, apoyo emocional y orientación. "
                "Mantén respuestas MUY cortas (1-2 oraciones). "
                "NO uses JSON, markdown, emojis ni formato especial."
            ))

    await session.start(
        room=ctx.room,
        agent=VoiceFiller(),
        room_input_options=RoomInputOptions(audio_enabled=True, close_on_disconnect=False),
        room_output_options=RoomOutputOptions(audio_enabled=True, transcription_enabled=True),
    )

    greeting = await kairos_respond(client_id, "")
    if not greeting:
        greeting = "Hola, soy tu asistente de voz Kairos. ¿En qué puedo ayudarte?"
    await session.generate_reply(instructions=greeting)

    logger.info("Voice session active for client=%s", client_id)
    await asyncio.Event().wait()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="kairos-voice"))
