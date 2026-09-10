"""Admin-only research preview, durable review, and anonymized export routes."""

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from config.logging import get_logger
from core.deps import get_db, require_admin
from core.time import serialize_utc_datetime, utc_now
from domain.entities.user import User
from domain.models.admin import ResearchSessionsEnvelope
from domain.models.research_annotation import (
    AnnotationExportRequest,
    AnnotationSetCompleteRequest,
    AnnotationSetCreateRequest,
    AnnotationSetRecord,
    AnnotationSetReopenRequest,
    AuthoredRelationCreateRequest,
    AuthoredRelationRevisionRequest,
    CoverageDeclarationWriteRequest,
    EvaluationRunRecord,
    EvaluationRunSummary,
    HumanAnnotationCreateRequest,
    HumanAnnotationRevisionRequest,
    ResearchEvaluationRunSaveRequest,
    ReviewDecisionWriteRequest,
)
from domain.models.research_evaluation import (
    ResearchEvaluationRequest,
    ResearchEvaluationResponse,
    ResearchEvaluatorDescriptorsResponse,
    ResearchExportRequest,
)
from services.research_evaluation_service import (
    ResearchEvaluationService,
    ResearchEvaluationServiceError,
)
from services.research_annotation_export_service import ResearchAnnotationExportService
from services.research_annotation_service import (
    ResearchAnnotationService,
    ResearchAnnotationServiceError,
)
from services.research_evaluation_run_service import (
    ResearchEvaluationRunService,
    ResearchEvaluationRunServiceError,
)
from services.research_export_service import ResearchExportService
from services.research_service import ResearchService, resolve_anon_to_session_id

logger = get_logger(__name__)
router = APIRouter(prefix="/research", tags=["research"])


def _raise_research_evaluation_http_error(error: ResearchEvaluationServiceError) -> None:
    status_by_category = {
        "session_not_found": 404,
        "session_incomplete": 409,
        "invalid_evaluator": 422,
        "invalid_request": 422,
        "response_too_large": 413,
    }
    raise HTTPException(
        status_code=status_by_category[error.category],
        detail=str(error),
    ) from error


def _raise_evaluation_run_http_error(error: ResearchEvaluationRunServiceError) -> None:
    status_by_category = {
        "run_not_found": 404,
        "evaluation_failed": 502,
        "live_execution_refused": 409,
        "unsupported_annotation_policy": 422,
        "persistence_failed": 500,
    }
    raise HTTPException(
        status_code=status_by_category[error.category],
        detail={"category": error.category, "message": str(error)},
    ) from error


def _raise_annotation_http_error(error: ResearchAnnotationServiceError) -> None:
    status_by_category = {
        "annotation_set_not_found": 404,
        "annotation_set_forbidden": 403,
        "annotation_set_locked": 409,
        "no_reviewable_predictions": 422,
        "invalid_guideline": 422,
        "invalid_prediction": 422,
        "invalid_decision": 422,
        "invalid_correction": 422,
        "revision_conflict": 409,
        "completion_blocked": 409,
        "invalid_transition": 409,
        "invalid_selection": 422,
        "invalid_annotation": 422,
        "invalid_relation": 422,
        "invalid_coverage": 422,
        "persistence_failed": 500,
    }
    detail: dict[str, object] = {
        "category": error.category,
        "message": str(error),
    }
    if error.current_set_revision is not None:
        detail["current_set_revision"] = error.current_set_revision
    if error.current_decision_revision is not None:
        detail["current_decision_revision"] = error.current_decision_revision
    raise HTTPException(status_code=status_by_category[error.category], detail=detail) from error


@router.get("/evaluators", response_model=ResearchEvaluatorDescriptorsResponse)
async def get_research_evaluators(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """Return capability manifests for explicitly registered research evaluators."""

    return ResearchEvaluationService(db).descriptors()


@router.post(
    "/sessions/{session_id}/evaluations",
    response_model=ResearchEvaluationResponse,
)
async def evaluate_research_session(
    session_id: int,
    request: ResearchEvaluationRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """Run independent admin-authorized evaluations without persistence."""

    try:
        return await ResearchEvaluationService(db).evaluate(session_id, request)
    except ResearchEvaluationServiceError as error:
        _raise_research_evaluation_http_error(error)


@router.post(
    "/sessions/{session_id}/evaluation-runs",
    response_model=EvaluationRunRecord,
)
async def run_and_save_research_evaluation(
    session_id: int,
    request: ResearchEvaluationRunSaveRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """Execute one evaluator server-side and save its immutable validated result."""

    try:
        record = await ResearchEvaluationRunService(db).run_and_save(
            session_id, request, current_user
        )
    except ResearchEvaluationServiceError as error:
        _raise_research_evaluation_http_error(error)
    except ResearchEvaluationRunServiceError as error:
        _raise_evaluation_run_http_error(error)
    logger.info(
        "Research evaluation run saved admin_user_id=%s session_id=%s run_uuid=%s",
        current_user.id,
        session_id,
        record.run_uuid,
    )
    return record


@router.get(
    "/sessions/{session_id}/evaluation-runs",
    response_model=tuple[EvaluationRunSummary, ...],
)
async def list_saved_research_evaluations(
    session_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """List immutable research runs associated with one source session."""

    return ResearchEvaluationRunService(db).list_for_session(session_id)


@router.get(
    "/evaluation-runs/{run_uuid}",
    response_model=EvaluationRunRecord,
)
async def get_saved_research_evaluation(
    run_uuid: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    try:
        return ResearchEvaluationRunService(db).get_run(run_uuid)
    except ResearchEvaluationRunServiceError as error:
        _raise_evaluation_run_http_error(error)


@router.post(
    "/evaluation-runs/{run_uuid}/annotation-sets",
    response_model=AnnotationSetRecord,
)
async def create_research_annotation_set(
    run_uuid: UUID,
    request: AnnotationSetCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    try:
        return ResearchAnnotationService(db).create_annotation_set(
            run_uuid, request, current_user
        )
    except ResearchAnnotationServiceError as error:
        _raise_annotation_http_error(error)


@router.get(
    "/annotation-sets/{annotation_set_uuid}",
    response_model=AnnotationSetRecord,
)
async def get_research_annotation_set(
    annotation_set_uuid: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    try:
        return ResearchAnnotationService(db).get_annotation_set(annotation_set_uuid)
    except ResearchAnnotationServiceError as error:
        _raise_annotation_http_error(error)


@router.put(
    "/annotation-sets/{annotation_set_uuid}/decisions/{prediction_id}",
    response_model=AnnotationSetRecord,
)
async def save_research_review_decision(
    annotation_set_uuid: UUID,
    prediction_id: str,
    request: ReviewDecisionWriteRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    try:
        return ResearchAnnotationService(db).record_decision(
            annotation_set_uuid, prediction_id, request, current_user
        )
    except (ResearchAnnotationServiceError, ResearchEvaluationRunServiceError) as error:
        if isinstance(error, ResearchAnnotationServiceError):
            _raise_annotation_http_error(error)
        _raise_evaluation_run_http_error(error)


@router.post("/annotation-sets/{annotation_set_uuid}/annotations", response_model=AnnotationSetRecord)
async def create_human_annotation(
    annotation_set_uuid: UUID,
    request: HumanAnnotationCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    try:
        return ResearchAnnotationService(db).create_human_annotation(annotation_set_uuid, request, current_user)
    except ResearchAnnotationServiceError as error:
        _raise_annotation_http_error(error)


@router.post("/annotation-sets/{annotation_set_uuid}/annotations/{annotation_id}/revisions", response_model=AnnotationSetRecord)
async def revise_human_annotation(
    annotation_set_uuid: UUID,
    annotation_id: str,
    request: HumanAnnotationRevisionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    try:
        return ResearchAnnotationService(db).revise_human_annotation(annotation_set_uuid, annotation_id, request, current_user)
    except ResearchAnnotationServiceError as error:
        _raise_annotation_http_error(error)


@router.post("/annotation-sets/{annotation_set_uuid}/relations", response_model=AnnotationSetRecord)
async def create_authored_relation(
    annotation_set_uuid: UUID,
    request: AuthoredRelationCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    try:
        return ResearchAnnotationService(db).create_authored_relation(annotation_set_uuid, request, current_user)
    except ResearchAnnotationServiceError as error:
        _raise_annotation_http_error(error)


@router.post("/annotation-sets/{annotation_set_uuid}/relations/{relation_id}/revisions", response_model=AnnotationSetRecord)
async def revise_authored_relation(
    annotation_set_uuid: UUID,
    relation_id: str,
    request: AuthoredRelationRevisionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    try:
        return ResearchAnnotationService(db).revise_authored_relation(annotation_set_uuid, relation_id, request, current_user)
    except ResearchAnnotationServiceError as error:
        _raise_annotation_http_error(error)


@router.post("/annotation-sets/{annotation_set_uuid}/coverage", response_model=AnnotationSetRecord)
async def declare_annotation_coverage(
    annotation_set_uuid: UUID,
    request: CoverageDeclarationWriteRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    try:
        return ResearchAnnotationService(db).declare_coverage(annotation_set_uuid, request, current_user)
    except ResearchAnnotationServiceError as error:
        _raise_annotation_http_error(error)


@router.post(
    "/annotation-sets/{annotation_set_uuid}/complete",
    response_model=AnnotationSetRecord,
)
async def complete_research_annotation_set(
    annotation_set_uuid: UUID,
    request: AnnotationSetCompleteRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    try:
        return ResearchAnnotationService(db).complete(
            annotation_set_uuid, request, current_user
        )
    except ResearchAnnotationServiceError as error:
        _raise_annotation_http_error(error)


@router.post(
    "/annotation-sets/{annotation_set_uuid}/reopen",
    response_model=AnnotationSetRecord,
)
async def reopen_research_annotation_set(
    annotation_set_uuid: UUID,
    request: AnnotationSetReopenRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    try:
        return ResearchAnnotationService(db).reopen(
            annotation_set_uuid, request, current_user
        )
    except ResearchAnnotationServiceError as error:
        _raise_annotation_http_error(error)


@router.post("/annotation-sets/{annotation_set_uuid}/exports")
async def export_research_annotation_set(
    annotation_set_uuid: UUID,
    request: AnnotationExportRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    annotation_service = ResearchAnnotationService(db)
    run_service = annotation_service.run_service
    try:
        artifact = ResearchAnnotationExportService(
            annotation_service, run_service
        ).render(annotation_set_uuid, request)
    except ResearchAnnotationServiceError as error:
        _raise_annotation_http_error(error)
    except ResearchEvaluationRunServiceError as error:
        _raise_evaluation_run_http_error(error)
    logger.info(
        "Research annotation export admin_user_id=%s annotation_set_uuid=%s profile=%s transcript=%s",
        current_user.id,
        annotation_set_uuid,
        request.profile,
        request.include_transcript_content,
    )
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'},
    )


@router.post("/sessions/{session_id}/evaluation-exports")
async def export_research_evaluations(
    session_id: int,
    request: ResearchExportRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """Export validated run results; this endpoint never executes an evaluator."""

    service = ResearchEvaluationService(db)
    try:
        transcript_turns, transcript_identity = service.completed_transcript(session_id)
    except ResearchEvaluationServiceError as error:
        _raise_research_evaluation_http_error(error)
    if any(
        envelope.transcript.canonical_transcript_hash
        != transcript_identity.canonical_transcript_hash
        for envelope in request.envelopes
    ):
        raise HTTPException(
            status_code=422,
            detail="Export envelope transcript hash does not match the selected session.",
        )
    artifact = ResearchExportService().render(request, transcript_turns)
    logger.info(
        "Research evaluation export admin_user_id=%s session_id=%s profile=%s",
        current_user.id,
        session_id,
        request.profile,
    )
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
        },
    )


@router.get("/sessions", response_model=ResearchSessionsEnvelope)
async def get_sessions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """Return list of anonymized sessions (no PII, admin only)."""
    service = ResearchService(db)
    sessions = service.get_all_sessions(skip=skip, limit=limit)
    return {"sessions": sessions, "total": len(sessions), "skip": skip, "limit": limit}


@router.get("/sessions/{anon_session_id}")
async def get_session(
    anon_session_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """Return anonymized session details by anon_session_id (no PII, admin only)."""
    service = ResearchService(db)
    try:
        session_data = service.get_session_by_anon(anon_session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_data


@router.get("/export")
async def export_research_data(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """Return downloadable JSON export of anonymized research data (admin only)."""
    service = ResearchService(db)
    json_content = service.get_export_json_content()
    record_count = len(json.loads(json_content))
    logger.info(
        "Research export triggered admin_user_id=%s timestamp=%s sessions_exported=%s",
        current_user.id,
        serialize_utc_datetime(utc_now()),
        record_count,
    )
    return Response(
        content=json_content,
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="research_export.json"',
        },
    )


@router.get("/export/metrics.csv")
async def export_metrics_csv(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """Stream metrics CSV: one row per session (admin only)."""
    service = ResearchService(db)
    logger.info(
        "Research metrics CSV export admin_user_id=%s timestamp=%s",
        current_user.id,
        serialize_utc_datetime(utc_now()),
    )
    return StreamingResponse(
        service.stream_metrics_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="session_metrics.csv"',
        },
    )


@router.get("/export/transcripts.csv")
async def export_transcripts_csv(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """Stream all transcripts CSV: flattened rows with anonymized text (admin only)."""
    service = ResearchService(db)
    logger.info(
        "Research transcripts CSV export admin_user_id=%s timestamp=%s",
        current_user.id,
        serialize_utc_datetime(utc_now()),
    )
    return StreamingResponse(
        service.stream_transcripts_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="all_transcripts.csv"',
        },
    )


@router.get("/export/session/{anon_session_id}.csv")
async def export_session_transcript_csv(
    anon_session_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """Stream single session transcript CSV by anon_session_id (admin only)."""
    service = ResearchService(db)
    # Resolve before StreamingResponse: generator body runs on first read, so ValueError
    # there would surface as 500 instead of 404.
    if resolve_anon_to_session_id(anon_session_id, service.session_repo) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    safe_anon = "".join(c if c.isalnum() or c == "_" else "_" for c in anon_session_id)[:32]
    return StreamingResponse(
        service.stream_session_transcript_csv(anon_session_id),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="session_{safe_anon}.csv"',
        },
    )


@router.get("/export.csv")
async def export_research_csv(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """Return downloadable CSV export of anonymized flattened session+turns (admin only)."""
    service = ResearchService(db)
    csv_content = service.get_export_csv_content()
    logger.info(
        "Research CSV export triggered admin_user_id=%s timestamp=%s",
        current_user.id,
        serialize_utc_datetime(utc_now()),
    )
    return StreamingResponse(
        iter([csv_content.encode("utf-8")]),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="research_export.csv"',
        },
    )
