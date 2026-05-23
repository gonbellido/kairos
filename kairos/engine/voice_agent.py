"""LiveKit Voice Agent — with correct room_input_options and debug listeners."""

import httpx
import logging
import os
import sys

from livekit import rtc
from livekit.agents import (
    Agent, AgentSession, AutoSubscribe, JobContext, WorkerOptions, cli,
    RoomInputOptions, RoomOutputOptions,
)
from livekit.plugins import silero, deepgram, openai, cartesia

KAIROS_API = os.environ.get("KAIROS_API_URL", "http://app:8000")

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("kairos.voice")


class KairosVoiceAssistant(Agent):
    def __init__(self, voice_prompt: str = "") -> None:
        instructions = voice_prompt or (
            "Eres un asistente de coaching de voz de KAIROS, cálido y empático. "
            "Ayudas a clientes con crecimiento personal, apoyo emocional y orientación. "
            "Mantén respuestas MUY cortas (1-2 oraciones), naturales y conversacionales. "
            "Habla como un coach humano en una conversación de voz. "
            "NO uses JSON, markdown, emojis ni formato especial. "
            "En español, la 'h' es muda. 'Hola' se dice 'ola', no 'jola'. "
            "Kairos se pronuncia 'Kai-ros', no deletreado."
        )
        super().__init__(instructions=instructions)


async def entrypoint(ctx: JobContext):
    client_id = ctx.room.name.replace("client_", "")
    logger.info("Voice session starting for client=%s room=%s", client_id, ctx.room.name)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Look up voice journey system prompt for this client
    voice_prompt = ""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{KAIROS_API}/api/v1/voice/journey-prompt",
                            params={"client_id": client_id})
            if r.status_code == 200:
                data = r.json()
                voice_prompt = data.get("system_prompt", "")
                logger.info("Voice journey prompt loaded (%d chars)", len(voice_prompt))
    except Exception as e:
        logger.warning("Voice journey lookup failed: %s", e)

    openai_api_key = os.environ.get("LLM_API_KEY", "")
    openai_base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")
    openai_model = os.environ.get("LLM_MODEL", "deepseek-chat")
    cartesia_key = os.environ.get("CARTESIA_API_KEY", "")
    cartesia_voice = os.environ.get("CARTESIA_VOICE_ID",
                                     "694f9389-aac1-45b6-b726-9d9369183238")
    deepgram_key = os.environ.get("DEEPGRAM_API_KEY", "")

    stt_kwargs = {"model": "nova-2", "language": "es"}
    if deepgram_key:
        stt_kwargs["api_key"] = deepgram_key

    llm_kwargs = {"model": openai_model, "base_url": openai_base_url}
    if openai_api_key:
        llm_kwargs["api_key"] = openai_api_key

    session = AgentSession(
        stt=deepgram.STT(**stt_kwargs),
        llm=openai.LLM(**llm_kwargs),
        tts=cartesia.TTS(voice=cartesia_voice, api_key=cartesia_key) if cartesia_key else None,
        vad=silero.VAD.load(),
    )

    # Debug event listeners
    @session.on("user_input_transcribed")
    def _on_transcript(ev):
        logger.info(">>> transcript: %s final=%s", ev.transcript, ev.is_final)

    @ctx.room.on("track_subscribed")
    def _on_track_sub(track: rtc.Track, pub: rtc.RemoteTrackPublication, p: rtc.RemoteParticipant):
        logger.info("SUBSCRIBED kind=%s from=%s", track.kind, p.identity)

    @ctx.room.on("participant_connected")
    def _on_participant_join(p: rtc.RemoteParticipant):
        logger.info("PARTICIPANT JOINED: %s", p.identity)

    await session.start(
        room=ctx.room,
        agent=KairosVoiceAssistant(voice_prompt=voice_prompt),
        room_input_options=RoomInputOptions(
            audio_enabled=True,
            close_on_disconnect=False,
        ),
        room_output_options=RoomOutputOptions(
            audio_enabled=True,
            transcription_enabled=True,
        ),
    )

    await session.generate_reply(
        instructions="Saluda al cliente en español. "
                     "Di: 'Ola, soy tu asistente de voz Kairos. ¿En qué puedo ayudarte?'",
    )

    logger.info("Voice session active for client=%s", client_id)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="kairos-voice"))
