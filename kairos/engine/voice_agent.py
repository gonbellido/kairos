"""LiveKit Voice Agent — simple voice coaching assistant using KAIROS pipeline."""

import asyncio
import logging
import os
import sys

from livekit import agents
from livekit.agents import AgentServer, AgentSession, Agent, room_io
from livekit.plugins import silero, deepgram, openai, cartesia

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("kairos.voice")

server = AgentServer()


class KairosVoiceAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "Eres un asistente de coaching de voz de KAIROS, cálido y empático. "
                "Ayudas a clientes con crecimiento personal, apoyo emocional y orientación. "
                "Mantén respuestas MUY cortas (1-2 oraciones), naturales y conversacionales. "
                "Habla como un coach humano en una conversación de voz, no como un robot. "
                "NO uses JSON, markdown, emojis ni formato especial. Solo texto plano natural."
            )
        )


@server.rtc_session(agent_name="kairos-voice")
async def voice_session(ctx: agents.JobContext):
    client_id = ctx.room.name.replace("client_", "")
    logger.info("Voice session starting for client=%s room=%s", client_id, ctx.room.name)

    openai_api_key = os.environ.get("LLM_API_KEY", "")
    openai_base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")
    openai_model = os.environ.get("LLM_MODEL", "deepseek-chat")
    cartesia_key = os.environ.get("CARTESIA_API_KEY", "")
    cartesia_voice = os.environ.get("CARTESIA_VOICE_ID",
                                     "694f9389-aac1-45b6-b726-9d9369183238")
    deepgram_key = os.environ.get("DEEPGRAM_API_KEY", "")

    stt_kwargs = {"model": "nova-3", "language": "multi"}
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

    await session.start(
        room=ctx.room,
        agent=KairosVoiceAssistant(),
    )

    await session.generate_reply(
        instructions="Saluda al cliente en español. Di 'Kairos' como una palabra. "
                     "Di: 'Hola, soy tu asistente de voz Kairos. ¿En qué puedo ayudarte?'",
    )

    logger.info("Voice session active for client=%s", client_id)
    await asyncio.Event().wait()


if __name__ == "__main__":
    agents.cli.run_app(server)
