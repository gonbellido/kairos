from datetime import datetime, timezone
from typing import Any

_utcnow = lambda: datetime.now(tz=timezone.utc)
import logging

from kairos.core.state import AgentState, Decision
from kairos.core.memory import RawMemory
from kairos.memory.stores.raw_store import RawStore
from kairos.engine.audio.transcriber import AudioTranscriber

logger = logging.getLogger(__name__)


async def audio_ingestion_node(
    state: AgentState,
    transcriber: AudioTranscriber,
    raw_store: RawStore,
) -> dict[str, Any]:
    audio_data: bytes | None = state.get("context", {}).get("_audio_bytes")
    audio_path: str | None = state.get("context", {}).get("_audio_path")

    if not audio_data and not audio_path:
        return {"next_agent": "perception", "decisions": [{
            "agent": "audio_ingestion",
            "action": "skip",
            "reasoning": "No audio data in context",
            "timestamp": _utcnow().isoformat(),
            "data_snapshot": {},
        }]}

    if not transcriber.available:
        logger.warning("Whisper not available, skipping transcription")
        return {"next_agent": "perception"}

    try:
        if audio_path:
            result = await transcriber.transcribe(str(audio_path))
        else:
            result = await transcriber.transcribe_bytes(audio_data)

        text = result.get("text", "")
        if not text.strip():
            logger.warning("Transcription returned empty text")
            return {"next_agent": "perception"}

        raw = RawMemory(
            profile_id=state.get("profile_id", "default"),
            content=text,
            source_type="audio_transcription",
            metadata={
                "language": result.get("language", "es"),
                "duration": result.get("duration", 0),
                "segments": len(result.get("segments", [])),
            },
        )
        raw_id = await raw_store.store(raw)
        logger.info("Stored raw memory from audio: %s", raw_id)

        # Replace message with transcription so the pipeline processes it
        return {
            "message": text,
            "next_agent": "perception",
            "decisions": [{
                "agent": "audio_ingestion",
                "action": "transcribe",
                "reasoning": f"Audio transcribed ({result.get('duration', 0):.1f}s)",
                "timestamp": _utcnow().isoformat(),
                "data_snapshot": {"raw_id": raw_id, "text_len": len(text)},
            }],
        }

    except Exception as e:
        logger.error("Transcription failed: %s", e)
        return {"next_agent": "perception"}
