"""Whisper ASR adapter implementation."""

import tempfile
from pathlib import Path

from openai import AsyncOpenAI

from config.logging import get_logger
from config.settings import get_settings
from core.errors import ExternalServiceError, ValidationError

logger = get_logger(__name__)


class WhisperAdapter:
    """Adapter for OpenAI Whisper ASR."""
    
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.model_id = settings.openai_asr_model_id
        self.client = AsyncOpenAI(api_key=self.api_key)
    
    async def transcribe_audio(
        self,
        audio_data: bytes,
        audio_format: str = "wav",
    ) -> str:
        """Transcribe audio using Whisper API."""
        if not audio_data:
            raise ValidationError("Audio file is empty")

        try:
            # Write audio to temporary file (Whisper API requires file input)
            with tempfile.NamedTemporaryFile(
                suffix=f".{audio_format}",
                delete=False,
            ) as temp_audio:
                temp_audio.write(audio_data)
                temp_path = Path(temp_audio.name)
            
            try:
                # Transcribe using Whisper
                # temperature=0 is only sent to whisper-1, where it was
                # always used; newer transcribe models get their defaults.
                extra: dict = {"temperature": 0} if self.model_id == "whisper-1" else {}
                with open(temp_path, "rb") as audio_file:
                    transcript = await self.client.audio.transcriptions.create(
                        model=self.model_id,
                        file=audio_file,
                        **extra,
                    )

                transcript_text = (transcript.text or "").strip()
                if not transcript_text:
                    raise ValidationError("Could not detect speech in the uploaded audio")

                return transcript_text
            finally:
                # Clean up temporary file
                temp_path.unlink(missing_ok=True)
                
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            raise ExternalServiceError("Audio transcription failed") from e

