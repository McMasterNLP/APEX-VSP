"""Sessions controller/router."""

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from adapters.audio_tone_adapter import AudioToneAdapter
from adapters.asr.whisper_adapter import WhisperAdapter
from adapters.llm.openai_adapter import OpenAIAdapter
from adapters.nlu.simple_rule_nlu import SimpleRuleNLU
from adapters.storage import get_storage_adapter
from adapters.tts import get_tts_adapter
from config.logging import get_logger
from config.settings import get_settings
from core.deps import get_current_user, get_db, verify_session_access
from core.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from core.time import utc_now
from domain.entities.user import User
from repositories.feedback_repo import FeedbackRepository
from repositories.session_repo import SessionRepository
from domain.models.sessions import (
    AudioToneAnalysis,
    FeedbackResponse,
    SessionCreate,
    SessionDetailResponse,
    SessionListResponse,
    SessionResponse,
    TurnCreate,
    TurnResponse,
    TurnResponseWithAudio,
)
from services.dialogue_service import DialogueService
from services.scoring_service import ScoringService
from services.session_service import SessionService
from services.usage_service import UsageService

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = get_logger(__name__)
ALLOWED_AUDIO_EXTENSIONS = {"wav", "ogg", "mp3", "webm", "m4a"}
MAX_AUDIO_UPLOAD_BYTES = 10 * 1024 * 1024


def _build_turn_audio_url(turn_id: int, audio_url: str | None, audio_expires_at=None) -> str | None:
    """Build the backend assistant audio endpoint URL when audio is available."""
    if not audio_url:
        return None
    if audio_expires_at is not None and audio_expires_at <= utc_now():
        return None
    base_url = get_settings().public_base_url.rstrip("/")
    return f"{base_url}/v1/turns/{turn_id}/audio"


def _deserialize_json_field(value: str | None) -> dict | list | None:
    """Deserialize JSON string to dict/list, or return None."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    # If already dict/list, return as-is (shouldn't happen, but safe)
    return value if isinstance(value, (dict, list)) else None


def _normalize_audio_extension(upload: UploadFile) -> str:
    """Get a supported extension from the uploaded file."""
    suffix = Path(upload.filename or "").suffix.lower().lstrip(".")
    if suffix in ALLOWED_AUDIO_EXTENSIONS:
        return suffix

    content_type = (upload.content_type or "").lower()
    content_type_map = {
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/ogg": "ogg",
        "audio/webm": "webm",
        "audio/mp4": "m4a",
        "audio/x-m4a": "m4a",
    }
    normalized = content_type_map.get(content_type)
    if normalized:
        return normalized

    raise ValidationError(
        f"Unsupported audio format. Allowed formats: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}"
    )


def _validate_audio_payload(audio_data: bytes) -> None:
    """Validate uploaded audio bytes."""
    if not audio_data:
        raise ValidationError("Audio file is empty")
    if len(audio_data) > MAX_AUDIO_UPLOAD_BYTES:
        raise ValidationError(
            f"Audio file is too large. Maximum size is {MAX_AUDIO_UPLOAD_BYTES // (1024 * 1024)} MB"
        )


def _validate_session_write_access(session_id: int, db: Session, current_user: User):
    """Ensure the current user can add turns to the session."""
    session_repo = SessionRepository(db)
    session = session_repo.get_by_id(session_id)
    if not session:
        raise NotFoundError(f"Session with ID {session_id} not found")
    if session.user_id != current_user.id:
        raise AuthorizationError("You do not have permission to update this session")
    if session.state != "active":
        raise ConflictError("Session is not active")
    return session


class AudioTranscriptionResponse(BaseModel):
    """Audio transcription payload before patient response generation."""
    transcript: str
    audio_tone: AudioToneAnalysis | None = None


async def _transcribe_and_analyze_audio(
    audio_file: UploadFile,
) -> tuple[str, dict | None]:
    """Run ASR and best-effort acoustic tone analysis on the uploaded audio."""
    audio_format = _normalize_audio_extension(audio_file)

    audio_data = await audio_file.read()
    _validate_audio_payload(audio_data)

    asr_adapter = WhisperAdapter()
    transcribed_text = await asr_adapter.transcribe_audio(
        audio_data,
        audio_format=audio_format,
    )
    audio_tone = await AudioToneAdapter().analyze_audio(
        audio_data,
        audio_format=audio_format,
        transcript=transcribed_text,
    )
    return transcribed_text, audio_tone


class TurnListResponse(BaseModel):
    """Paginated turn list."""
    turns: list[TurnResponse]
    total: int
    skip: int
    limit: int


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    session_data: SessionCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a new session for a case."""
    session_service = SessionService(db)
    return await session_service.create_session(current_user.id, session_data)


@router.post("/{session_id}/turns", response_model=TurnResponseWithAudio)
async def submit_turn(
    session_id: int,
    turn_data: TurnCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Submit trainee turn text; returns patient reply and updated SPIKES stage."""
    session_repo = SessionRepository(db)
    sess = session_repo.get_by_id(session_id)
    if not sess:
        raise NotFoundError(f"Session with ID {session_id} not found")
    verify_session_access(sess, current_user)
    UsageService(db).check_and_record("chat_turn", current_user.id)

    # Initialize services
    llm_adapter = OpenAIAdapter()
    nlu_adapter = SimpleRuleNLU()
    dialogue_service = DialogueService(
        db,
        llm_adapter,
        nlu_adapter,
        tts_adapter=get_tts_adapter(),
        storage_adapter=get_storage_adapter(),
    )
    
    # Process turn and get patient response
    patient_turn = await dialogue_service.process_user_turn(session_id, turn_data)
    
    # Get updated session for SPIKES stage
    session_service = SessionService(db)
    session_detail = await session_service.get_session(session_id)
    resolved_assistant_audio_url = _build_turn_audio_url(
        patient_turn.id,
        patient_turn.audio_url,
        patient_turn.audio_expires_at,
    )
    
    return TurnResponseWithAudio(
        turn=patient_turn.model_copy(update={"audio_url": resolved_assistant_audio_url}),
        patient_reply=patient_turn.text,
        transcript=turn_data.text,
        audio_url=None,
        assistant_audio_url=resolved_assistant_audio_url,
        spikes_stage=session_detail.current_spikes_stage,
    )


@router.post("/{session_id}/audio", response_model=TurnResponseWithAudio)
async def submit_audio_turn(
    session_id: int,
    audio_file: Annotated[UploadFile, File(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    enable_tts: Annotated[bool, Form()] = False,
):
    """Upload audio file and process it as a normal conversation turn."""
    _validate_session_write_access(session_id, db, current_user)
    usage_service = UsageService(db)
    usage_service.check_and_record("audio", current_user.id)
    transcript, audio_tone = await _transcribe_and_analyze_audio(audio_file)

    # Process as turn
    turn_data = TurnCreate(
        text=transcript,
        voice_tone=audio_tone,
        enable_tts=enable_tts,
    )

    usage_service.check_and_record("chat_turn", current_user.id)

    # Initialize dialogue service
    llm_adapter = OpenAIAdapter()
    nlu_adapter = SimpleRuleNLU()
    dialogue_service = DialogueService(
        db,
        llm_adapter,
        nlu_adapter,
        tts_adapter=get_tts_adapter(),
        storage_adapter=get_storage_adapter(),
    )

    # Process turn
    patient_turn = await dialogue_service.process_user_turn(session_id, turn_data)

    # Get updated session
    session_service = SessionService(db)
    session_detail = await session_service.get_session(session_id)
    resolved_assistant_audio_url = _build_turn_audio_url(
        patient_turn.id,
        patient_turn.audio_url,
        patient_turn.audio_expires_at,
    )

    return TurnResponseWithAudio(
        turn=patient_turn.model_copy(update={"audio_url": resolved_assistant_audio_url}),
        patient_reply=patient_turn.text,
        transcript=transcript,
        audio_tone=audio_tone,
        audio_url=None,
        assistant_audio_url=resolved_assistant_audio_url,
        spikes_stage=session_detail.current_spikes_stage,
    )


@router.post("/{session_id}/audio:transcribe", response_model=AudioTranscriptionResponse)
async def transcribe_audio_turn(
    session_id: int,
    audio_file: Annotated[UploadFile, File(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Upload audio file and return only the transcript."""
    _validate_session_write_access(session_id, db, current_user)
    UsageService(db).check_and_record("audio", current_user.id)
    transcribed_text, audio_tone = await _transcribe_and_analyze_audio(audio_file)

    return AudioTranscriptionResponse(
        transcript=transcribed_text,
        audio_tone=audio_tone,
    )


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get session detail (state, metrics snapshot)."""
    session_repo = SessionRepository(db)
    sess = session_repo.get_by_id(session_id)
    if not sess:
        raise NotFoundError(f"Session with ID {session_id} not found")
    verify_session_access(sess, current_user)

    session_service = SessionService(db)
    return await session_service.get_session(session_id)


@router.get("/{session_id}/turns", response_model=TurnListResponse)
async def get_session_turns(
    session_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """Get paginated transcript of session turns."""
    session_repo = SessionRepository(db)
    sess = session_repo.get_by_id(session_id)
    if not sess:
        raise NotFoundError(f"Session with ID {session_id} not found")
    verify_session_access(sess, current_user)

    from repositories.turn_repo import TurnRepository

    turn_repo = TurnRepository(db)
    turns = turn_repo.get_by_session(session_id, skip=skip, limit=limit)
    total_turns = turn_repo.get_by_session(session_id)  # Get all for count
    
    return TurnListResponse(
        turns=[
            TurnResponse.model_validate(turn).model_copy(
                update={"audio_url": _build_turn_audio_url(turn.id, turn.audio_url, turn.audio_expires_at)}
            )
            for turn in turns
        ],
        total=len(total_turns),
        skip=skip,
        limit=limit,
    )


@router.post(
    "/{session_id}:close",
    response_model=FeedbackResponse,
    response_model_exclude_none=True,  # Exclude None values from response
)
async def close_session_and_get_feedback(
    session_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Close session and finalize feedback."""
    session_repo = SessionRepository(db)
    sess = session_repo.get_by_id(session_id)
    if not sess:
        raise NotFoundError(f"Session with ID {session_id} not found")
    verify_session_access(sess, current_user)

    # Close session
    session_service = SessionService(db)
    await session_service.close_session(session_id)

    # Generate and return feedback
    scoring_service = ScoringService(db)
    feedback = await scoring_service.generate_feedback(session_id)
    meta = feedback.evaluator_meta if isinstance(feedback.evaluator_meta, dict) else None
    logger.info(
        "session_close_feedback_generated",
        extra={
            "session_id": session_id,
            "evaluator_plugin_frozen": getattr(sess, "evaluator_plugin", None),
            "evaluator_meta_status": meta.get("status") if meta else None,
            "evaluator_meta_phase": meta.get("phase") if meta else None,
        },
    )
    return feedback


@router.get(
    "/{session_id}/feedback",
    response_model=FeedbackResponse,
    response_model_exclude_none=True,  # Exclude None values from response
)
async def get_session_feedback(
    session_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get feedback for a closed session."""
    # Get session and verify it exists
    session_repo = SessionRepository(db)
    session = session_repo.get_by_id(session_id)
    if not session:
        raise NotFoundError(f"Session with ID {session_id} not found")

    verify_session_access(session, current_user)
    
    # Get feedback
    feedback_repo = FeedbackRepository(db)
    feedback = feedback_repo.get_by_session(session_id)
    if not feedback:
        raise NotFoundError(f"Feedback not found for session {session_id}. Session may not be closed yet.")
    
    # Deserialize JSON fields before creating response (matching scoring_service pattern)
    feedback.eo_counts_by_dimension = _deserialize_json_field(feedback.eo_counts_by_dimension)
    feedback.elicitation_counts_by_type = _deserialize_json_field(feedback.elicitation_counts_by_type)
    feedback.response_counts_by_type = _deserialize_json_field(feedback.response_counts_by_type)
    feedback.linkage_stats = _deserialize_json_field(feedback.linkage_stats)
    feedback.missed_opportunities_by_dimension = _deserialize_json_field(feedback.missed_opportunities_by_dimension)
    feedback.eo_to_elicitation_links = _deserialize_json_field(feedback.eo_to_elicitation_links)
    feedback.eo_to_response_links = _deserialize_json_field(feedback.eo_to_response_links)
    feedback.missed_opportunities = _deserialize_json_field(feedback.missed_opportunities)
    feedback.spikes_coverage = _deserialize_json_field(feedback.spikes_coverage)
    feedback.spikes_timestamps = _deserialize_json_field(feedback.spikes_timestamps)
    feedback.spikes_strategies = _deserialize_json_field(feedback.spikes_strategies)
    feedback.question_breakdown = _deserialize_json_field(feedback.question_breakdown)
    feedback.bias_probe_info = _deserialize_json_field(feedback.bias_probe_info)
    feedback.evaluator_meta = _deserialize_json_field(feedback.evaluator_meta)
    
    # Set span-level fields to None (computed during generation, not stored)
    feedback.eo_spans = None
    feedback.elicitation_spans = None
    feedback.response_spans = None
    feedback.relations = None
    
    # Create response and let exclude_none=True and _remove_empty_values handle cleanup
    return FeedbackResponse.model_validate(feedback)


@router.get("", response_model=SessionListResponse)
async def list_user_sessions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    state: str = Query(..., regex="^(active|completed)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """List current user's sessions filtered by state."""
    session_service = SessionService(db)
    return await session_service.list_user_sessions(current_user.id, skip, limit, state=state)

