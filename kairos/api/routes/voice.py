"""Fase L: Voice endpoints — LiveKit token, TTS via Cartesia."""

import io
import logging
import os
import base64
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])


@router.get("/token")
async def get_voice_token(req: Request):
    """Generate LiveKit room token for a client. One room per client."""
    token = req.cookies.get("kairos_client_token")
    if not token:
        return JSONResponse({"error": "No autorizado"}, status_code=401)

    from kairos.engine.client_auth import ClientAuth
    auth = ClientAuth(req.app.state.runtime.client_store)
    client = await auth.get_client_by_token(token)
    if not client:
        return JSONResponse({"error": "Token inválido"}, status_code=401)

    client_id = client.id
    room_name = f"client_{client_id}"

    livekit_url = os.environ.get("LIVEKIT_URL", "")
    api_key = os.environ.get("LIVEKIT_API_KEY", "")
    api_secret = os.environ.get("LIVEKIT_API_SECRET", "")

    if not all([livekit_url, api_key, api_secret]):
        return JSONResponse({
            "ok": False,
            "error": "LiveKit not configured. Set LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET",
            "room": room_name,
            "url": livekit_url or "wss://livekit.ether.care",
        })

    try:
        from livekit import api as lk_api

        token_obj = lk_api.AccessToken(api_key, api_secret)
        token_obj.with_identity(f"client_{client_id}")
        token_obj.with_name(client.nombre or "Cliente")
        token_obj.with_grants(lk_api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        ))

        jwt = token_obj.to_jwt()

        return {
            "ok": True,
            "token": jwt,
            "room": room_name,
            "url": livekit_url,
        }
    except ImportError:
        return JSONResponse({
            "ok": False,
            "error": "livekit-api package not installed. Run: pip install livekit-api",
        })
    except Exception as e:
        logger.error("LiveKit token generation failed: %s", e)
        return JSONResponse({"ok": False, "error": str(e)})


@router.post("/tts")
async def text_to_speech(req: Request):
    """Generate TTS audio from text using Cartesia. Returns base64 WAV."""
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    text = body.get("text", "")
    if not text.strip():
        return JSONResponse({"error": "No text provided"}, status_code=400)

    api_key = os.environ.get("CARTESIA_API_KEY", "")
    voice_id = os.environ.get("CARTESIA_VOICE_ID", "694f9389-aac1-45b6-b726-9d9369183238")

    if not api_key:
        return JSONResponse({"error": "Cartesia not configured"}, status_code=500)

    try:
        from cartesia import Cartesia
        client = Cartesia(api_key=api_key)

        output_format = {"container": "wav", "encoding": "pcm_f32le", "sample_rate": 44100}

        response = client.tts.generate(
            model_id="sonic-3",
            transcript=text,
            voice={"mode": "id", "id": voice_id},
            language="es",
            output_format=output_format,
        )

        audio_bytes = b""
        for chunk in response.iter_bytes():
            audio_bytes += chunk

        b64 = base64.b64encode(audio_bytes).decode("utf-8")
        return {
            "ok": True,
            "audio": b64,
            "format": "wav",
            "sample_rate": 44100,
        }

    except ImportError:
        logger.error("cartesia SDK not installed")
        return JSONResponse({"error": "cartesia SDK not installed"}, status_code=500)
    except Exception as e:
        logger.error("TTS generation failed: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)
