"""Unit tests for WhisperAdapter (no real OpenAI calls)."""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("database_url", "sqlite:///./test_whisper_adapter.db")
os.environ.setdefault("secret_key", "test-secret")
os.environ.setdefault("supabase_jwt_secret", "test-supabase-jwt")
os.environ.setdefault("gemini_api_key", "test-gemini-key")
os.environ.setdefault("openai_api_key", "test-openai-key")

from adapters.asr.whisper_adapter import WhisperAdapter
from core.errors import ExternalServiceError, ValidationError


@pytest.mark.asyncio
async def test_whisper_rejects_empty_audio():
    adapter = WhisperAdapter()
    with pytest.raises(ValidationError, match="empty"):
        await adapter.transcribe_audio(b"", "wav")


@pytest.mark.asyncio
async def test_whisper_returns_stripped_transcript():
    adapter = WhisperAdapter()
    adapter.client = MagicMock()
    adapter.client.audio.transcriptions.create = AsyncMock(
        return_value=SimpleNamespace(text="  hello from whisper  ")
    )

    result = await adapter.transcribe_audio(b"\x00\x01", "wav")

    assert result == "hello from whisper"
    adapter.client.audio.transcriptions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_whisper_raises_when_transcript_blank():
    adapter = WhisperAdapter()
    adapter.client = MagicMock()
    adapter.client.audio.transcriptions.create = AsyncMock(
        return_value=SimpleNamespace(text="   \n\t  ")
    )

    with pytest.raises(ValidationError, match="Could not detect speech"):
        await adapter.transcribe_audio(b"\xff", "webm")


@pytest.mark.asyncio
async def test_whisper_maps_api_errors_to_external_service_error():
    adapter = WhisperAdapter()
    adapter.client = MagicMock()
    adapter.client.audio.transcriptions.create = AsyncMock(side_effect=RuntimeError("network"))

    with pytest.raises(ExternalServiceError, match="Audio transcription failed"):
        await adapter.transcribe_audio(b"data", "mp3")


def _mock_transcribe(adapter: WhisperAdapter) -> AsyncMock:
    create = AsyncMock(return_value=SimpleNamespace(text="ok"))
    adapter.client = MagicMock()
    adapter.client.audio.transcriptions.create = create
    return create


@pytest.mark.asyncio
async def test_default_asr_model_is_gpt_transcribe_without_temperature():
    adapter = WhisperAdapter()
    create = _mock_transcribe(adapter)

    await adapter.transcribe_audio(b"\x00\x01", "wav")

    kwargs = create.await_args.kwargs
    assert kwargs["model"] == "gpt-transcribe"
    assert "temperature" not in kwargs


@pytest.mark.asyncio
async def test_whisper_1_rollback_keeps_temperature_zero():
    adapter = WhisperAdapter()
    adapter.model_id = "whisper-1"
    create = _mock_transcribe(adapter)

    await adapter.transcribe_audio(b"\x00\x01", "wav")

    kwargs = create.await_args.kwargs
    assert kwargs["model"] == "whisper-1"
    assert kwargs["temperature"] == 0
