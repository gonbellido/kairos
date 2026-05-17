import logging
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


try:
    import whisper  # pip install openai-whisper
    _WHISPER_AVAILABLE = True
except ImportError:
    _WHISPER_AVAILABLE = False
    logger.warning("whisper not installed. Audio transcription disabled. pip install openai-whisper")


class AudioTranscriber:
    def __init__(self, model_name: str = "base"):
        self._model = None
        self._model_name = model_name
        self.available = _WHISPER_AVAILABLE

    def _get_model(self):
        if self._model is None and self.available:
            import whisper as _w
            logger.info("Loading whisper model: %s", self._model_name)
            self._model = _w.load_model(self._model_name)
        return self._model

    async def transcribe(self, audio_path: str | Path) -> dict[str, Any]:
        model = self._get_model()
        if not model:
            return {"text": "", "error": "whisper not available", "segments": []}

        path = str(audio_path)
        logger.info("Transcribing: %s", path)

        loop = __import__("asyncio").get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: model.transcribe(path, language="es")
        )

        return {
            "text": result.get("text", ""),
            "language": result.get("language", "es"),
            "segments": [
                {
                    "start": s.get("start", 0),
                    "end": s.get("end", 0),
                    "text": s.get("text", ""),
                }
                for s in result.get("segments", [])
            ],
            "duration": result.get("segments", [{}])[-1].get("end", 0) if result.get("segments") else 0,
        }

    async def transcribe_bytes(self, audio_bytes: bytes) -> dict[str, Any]:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            return await self.transcribe(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
