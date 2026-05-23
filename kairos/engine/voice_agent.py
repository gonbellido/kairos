"""LiveKit Voice Agent — STT (DeepGram) + LLM (DeepSeek/GPT) + TTS (Cartesia Sonic-3)
   with VAD (Silero), turn detection, noise cancellation, and KAIROS pipeline integration."""

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
            instructions="""Eres un asistente de coaching de voz de KAIROS, cálido y empático.
Ayudas a clientes con crecimiento personal, apoyo emocional y orientación.
Mantén respuestas concisas (2-3 oraciones máximo), naturales y conversacionales.
No uses emojis, asteriscos, hashtags ni formato markdown.
Habla como un coach humano, no como un robot.
Si el cliente parece frustrado o triste, sé especialmente empático.
Si el cliente está avanzando bien, sé alentador.""",
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
        instructions="Saluda al cliente cálidamente en español. Di 'Kairos' como una palabra, no deletrees. "
                     "Di: 'Hola, soy tu asistente de voz Kairos. ¿En qué puedo ayudarte hoy?'",
    )

    # Conversation loop — keep listening and responding
    while True:
        logger.info("Waiting for user input...")
        resp = await session.generate_reply(
            instructions="Responde al cliente de forma natural y conversacional. "
                         "Mantén respuestas de 2-3 oraciones. "
                         "Si el cliente se despide, despídete cordialmente.",
        )
        if resp is None:
            break
        logger.info("Agent responded, listening again...")


if __name__ == "__main__":
    agents.cli.run_app(server)
