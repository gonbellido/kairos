"""Etapa 6: LiveKit adapter stub — voice channel audio transport."""


async def send_audio(text: str, room_name: str, is_filler: bool = False) -> bool:
    """TTS + publish audio to LiveKit room. Returns True on success."""
    try:
        import os
        from cartesia import Cartesia

        api_key = os.getenv("CARTESIA_API_KEY", "")
        voice_id = os.getenv("CARTESIA_VOICE_ID", "694f9389-aac1-45b6-b726-9d9369183238")
        if not api_key:
            return False

        client = Cartesia(api_key=api_key)
        response = client.tts.generate(
            model_id="sonic-3",
            transcript=text,
            voice={"mode": "id", "id": voice_id},
            language="es",
            output_format={"container": "raw", "encoding": "pcm_f32le", "sample_rate": 24000},
        )

        # Collect audio bytes
        audio = b""
        for chunk in response.iter_bytes():
            audio += chunk

        # TODO: publish to LiveKit room
        # await livekit_room.publish_audio(room_name, audio, is_filler=is_filler)
        return bool(audio)

    except Exception:
        return False


async def interrupt_filler(room_name: str) -> None:
    """Interrupt any currently playing filler audio in the room."""
    # TODO: implement via LiveKit track interruption
    pass
