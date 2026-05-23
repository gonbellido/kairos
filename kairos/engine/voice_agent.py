"""LiveKit Voice Agent — STT (DeepGram) + LLM (DeepSeek/GPT) + TTS (Cartesia Sonic-3)
   with VAD (Silero), turn detection, noise cancellation, and KAIROS pipeline integration."""

import logging
import os
import sys

from livekit import agents
from livekit.agents import AgentServer, AgentSession, Agent, inference, room_io, TurnHandlingOptions
from livekit.plugins import ai_coustics, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

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

    stt_kwargs = {}
    if deepgram_key:
        stt_kwargs["api_key"] = deepgram_key

    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="multi", **stt_kwargs),
        llm=inference.LLM(
            model=f"openai/{openai_model}",
            base_url=openai_base_url,
            api_key=openai_api_key,
        ),
        tts=inference.TTS(
            model="cartesia/sonic-3",
            voice=cartesia_voice,
            api_key=cartesia_key,
        ),
        vad=silero.VAD.load(),
        turn_handling=TurnHandlingOptions(
            turn_detection=MultilingualModel(),
        ),
    )

    room_opts = room_io.RoomOptions(
        audio_input=room_io.AudioInputOptions(
            noise_cancellation=ai_coustics.audio_enhancement(
                model=ai_coustics.EnhancerModel.QUAIL_VF_S,
            ),
        ),
    )

    await session.start(
        room=ctx.room,
        agent=KairosVoiceAssistant(),
        room_options=room_opts,
    )

    await session.generate_reply(
        instructions="Saluda al cliente cálidamente en español. Di algo como: "
                     "'Hola, soy tu asistente de voz KAIROS. ¿En qué puedo ayudarte hoy?'",
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
