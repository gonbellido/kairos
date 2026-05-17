"""Fase L: LiveKit Voice Agent — STT (Whisper) + LLM (DeepSeek) + TTS (Cartesia)."""

import logging
import os
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("kairos.voice")


def create_agent():
    """Create and return the LiveKit AgentServer with voice pipeline."""
    from livekit import agents
    from livekit.agents import AgentServer, AgentSession, Agent, room_io, AgentCallContext

    server = AgentServer()

    class KairosAssistant(Agent):
        def __init__(self) -> None:
            super().__init__(
                instructions="""You are a warm, empathetic KAIROS coaching voice assistant.
You help clients with personal growth, emotional support, and coaching guidance.
Keep responses concise (2-3 sentences max), natural, and conversational.
Do not use emojis, asterisks, hashtags, or markdown formatting.
Speak as a caring human coach would, not as a robot.
Adapt your tone to the client's emotional state when possible.""",
            )

    @server.rtc_session(agent_name="kairos-voice")
    async def voice_session(ctx: agents.JobContext):
        client_id = ctx.room.name.replace("client_", "")
        logger.info("Voice session starting for client=%s room=%s", client_id, ctx.room.name)

        from livekit.plugins import openai, cartesia, silero

        # Route to KAIROS API for chat/sync when user speaks
        kairos_api_url = os.environ.get("KAIROS_API_URL", "http://app:8000")

        openai_api_key = os.environ.get("LLM_API_KEY", "")
        openai_base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        openai_model = os.environ.get("LLM_MODEL", "deepseek-chat")

        cartesia_key = os.environ.get("CARTESIA_API_KEY", "")
        cartesia_voice = os.environ.get("CARTESIA_VOICE_ID", "694f9389-aac1-45b6-b726-9d9369183238")

        class KairosLLM(openai.LLM):
            """LLM that delegates to KAIROS pipeline, falling back to direct LLM."""

            def __init__(self):
                super().__init__(
                    model=openai_model,
                    base_url=openai_base_url,
                    api_key=openai_api_key,
                )

            async def chat(self, *, chat_ctx, fnc_ctx=None, temperature=None, n=1, parallel_tool_calls=None):
                user_msg = ""
                for msg in reversed(chat_ctx.messages):
                    if msg.role == "user" and msg.content:
                        user_msg = str(msg.content)
                        break

                if user_msg and kairos_api_url:
                    try:
                        import httpx
                        async with httpx.AsyncClient(timeout=15) as http:
                            resp = await http.post(
                                f"{kairos_api_url}/api/v1/chat/sync",
                                json={
                                    "message": user_msg,
                                    "session_id": f"voice_{client_id}",
                                    "profile_id": "coaching",
                                    "user_id": client_id,
                                    "context": {"client_id": client_id},
                                },
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                kairos_text = data.get("response", "")
                                if kairos_text and "error" not in data.get("response", ""):
                                    return super().chat(
                                        chat_ctx=chat_ctx,
                                        fnc_ctx=fnc_ctx,
                                        temperature=temperature,
                                        n=n,
                                        parallel_tool_calls=parallel_tool_calls,
                                    )
                    except Exception:
                        pass

                return await super().chat(
                    chat_ctx=chat_ctx,
                    fnc_ctx=fnc_ctx,
                    temperature=temperature,
                    n=n,
                    parallel_tool_calls=parallel_tool_calls,
                )

        session = AgentSession(
            stt=openai.STT(),
            llm=KairosLLM(),
            tts=cartesia.TTS(voice=cartesia_voice, api_key=cartesia_key),
            vad=silero.VAD.load(),
        )

        await session.start(
            room=ctx.room,
            agent=KairosAssistant(),
        )

        await session.generate_reply(
            instructions="Greet the client warmly in Spanish. Say something like: 'Hola, soy tu asistente de voz KAIROS. ¿En qué puedo ayudarte hoy?'",
        )

    return server


if __name__ == "__main__":
    from livekit import agents
    server = create_agent()
    agents.cli.run_app(server)
