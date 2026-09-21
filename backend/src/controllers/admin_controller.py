"""Admin controller/router."""

import json
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text  
from sqlalchemy.orm import Session

from config.settings import get_settings
from core.deps import get_db, require_admin, require_admin_or_researcher
from core.security import RoleScopes
from domain.entities.user import User
from core.time import UTCDateTime
from domain.models.admin import (
    AdminUserOverviewResponse,
    AdminUserOverviewRow,
    AdminUserRoleUpdateRequest,
    AnalyticsDashboard,
)
from domain.models.usage import CategoryUsageResponse, UsageAdminResponse, UsageTrendDay
from plugins.registry import PluginRegistry
from domain.entities.case import Case as CaseEntity
from domain.models.cases import CaseCreate, CaseResponse
from domain.models.sessions import SessionDetailResponse
from repositories.feedback_repo import FeedbackRepository
from repositories.user_repo import UserRepository
from services.analytics_service import AnalyticsService
from services.case_service import CaseService
from services.research_service import pseudonymous_participant_reference
from services.session_service import SessionService
from services.usage_service import UsageService

router = APIRouter(prefix="/admin", tags=["admin"])


def _with_session_user_info(
    detail: SessionDetailResponse, row: User | None, *, redact_identity: bool
) -> SessionDetailResponse:
    """Attach email/name from the users table for admin UI (not stored on session).

    @remarks
    `redact_identity=True` swaps the real name/email for a stable pseudonymous
    participant reference instead. This is for researcher-role callers: the
    evaluation/annotation pipeline needs the real transcript to score and review
    against, but never needs the trainee's real identity to do that work, so a
    researcher sees the same session and transcript content an admin does, just
    without the name and email attached. Admins (`redact_identity=False`) keep
    seeing real identity, matching today's behavior.
    """
    if not row:
        return detail
    if redact_identity:
        return detail.model_copy(
            update={
                "user_email": None,
                "user_full_name": pseudonymous_participant_reference(row.id),
            }
        )
    return detail.model_copy(
        update={
            "user_email": row.email,
            "user_full_name": row.full_name,
        }
    )


class AdminSessionListResponse(BaseModel):
    """Admin session list with filters."""
    sessions: list[SessionDetailResponse]
    total: int
    skip: int
    limit: int


#: Valid values for the `evaluation_status` sessions-list filter -- matches the
#: Sessions-list status chip's own labels exactly (see `_evaluation_status_bucket`).
EVALUATION_STATUS_FILTER_VALUES = ("no_runs", "needs_review", "in_review", "locked")


class SessionFilterCaseOption(BaseModel):
    """One case, for the Sessions-list case filter dropdown."""
    id: int
    title: str


class SessionFilterEvaluatorOption(BaseModel):
    """One person who has evaluated at least one session, for the evaluator filter
    dropdown. Evaluators are admin/researcher accounts reviewing on their own behalf,
    not trainees, so a real name/email here carries none of the trainee-identity
    redaction concerns `_with_session_user_info` exists for.
    """
    id: int
    label: str


class SessionFilterOptionsResponse(BaseModel):
    """Dropdown option lists for the Sessions-list filter bar, in one round trip."""
    cases: list[SessionFilterCaseOption]
    patient_plugins: list[str]
    evaluator_plugins: list[str]
    evaluators: list[SessionFilterEvaluatorOption]


class MetricsTimeline(BaseModel):
    """Metrics timeline for a session."""
    turn_number: int
    timestamp: UTCDateTime
    empathy_score: float
    question_type: str
    spikes_stage: str


class AdminFeedbackSummary(BaseModel):
    """Feedback summary for admin session detail (no ownership restriction)."""
    empathy_score: float
    overall_score: float
    strengths: Optional[str] = None
    areas_for_improvement: Optional[str] = None


class AdminSessionDetail(BaseModel):
    """Admin session detail with transcript, metrics, and feedback summary."""
    session: SessionDetailResponse
    feedback: Optional[AdminFeedbackSummary] = None
    metrics_timeline: list[MetricsTimeline]


class PluginsResponse(BaseModel):
    """Active plugin paths (module:ClassName) for admin visibility."""
    patient_model: str
    evaluator: str
    metrics: list[str]


class PluginInfo(BaseModel):
    """Name and version of a registered plugin."""
    name: str
    version: str


class PluginDiscoveryResponse(BaseModel):
    """Plugin discovery: registered evaluators, patient_models, and metrics with name+version."""
    evaluators: list[PluginInfo]
    patient_models: list[PluginInfo]
    metrics: list[PluginInfo]


@router.get("/plugin-registry", response_model=PluginDiscoveryResponse)
async def get_plugin_registry(
    current_user: Annotated[User, Depends(require_admin)],
):
    """Return registered plugins from PluginRegistry (name + version). Used for discovery and case override UI."""
    evaluators = []
    for plugin_cls in PluginRegistry.list_evaluators().values():
        evaluators.append(
            PluginInfo(name=getattr(plugin_cls, "name", ""), version=getattr(plugin_cls, "version", ""))
        )
    patient_models = []
    for plugin_cls in PluginRegistry.list_patient_models().values():
        patient_models.append(
            PluginInfo(name=getattr(plugin_cls, "name", ""), version=getattr(plugin_cls, "version", ""))
        )
    metrics = []
    for plugin_cls in PluginRegistry.list_metrics_plugins().values():
        metrics.append(
            PluginInfo(name=getattr(plugin_cls, "name", ""), version=getattr(plugin_cls, "version", ""))
        )
    return PluginDiscoveryResponse(evaluators=evaluators, patient_models=patient_models, metrics=metrics)


@router.get("/plugins", response_model=PluginsResponse)
async def get_active_plugins(
    current_user: Annotated[User, Depends(require_admin)],
):
    """Return configured plugin paths (admin only). Used by Admin UI Developer Tools."""
    settings = get_settings()
    return PluginsResponse(
        patient_model=settings.patient_model_plugin,
        evaluator=settings.evaluator_plugin,
        metrics=list(settings.metrics_plugins or []),
    )


@router.get("/health/db")
async def db_health(
    db: Annotated[Session, Depends(get_db)],
):
    """Simple DB health check."""
    db.execute(text("SELECT 1"))
    return {"db_ok": True}


@router.get("/sessions/filter-options", response_model=SessionFilterOptionsResponse)
async def get_session_filter_options(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin_or_researcher)],
):
    """Dropdown option lists for the Sessions-list filter bar (cases, patient/evaluator
    plugins actually in use, and who has evaluated at least one session).

    @remarks
    Declared before `/sessions/{session_id}` so "filter-options" is never matched as a
    session id.
    """
    from repositories.session_repo import SessionRepository

    session_repo = SessionRepository(db)
    cases = (
        db.query(CaseEntity.id, CaseEntity.title).order_by(CaseEntity.title).all()
    )
    evaluator_ids = session_repo.distinct_evaluator_user_ids()
    evaluators_by_id: dict[int, User] = {}
    if evaluator_ids:
        for u in db.query(User).filter(User.id.in_(evaluator_ids)).all():
            evaluators_by_id[u.id] = u

    return SessionFilterOptionsResponse(
        cases=[SessionFilterCaseOption(id=cid, title=title) for cid, title in cases],
        patient_plugins=session_repo.distinct_patient_plugins(),
        evaluator_plugins=session_repo.distinct_evaluator_plugins(),
        evaluators=[
            SessionFilterEvaluatorOption(
                id=uid,
                label=(evaluators_by_id[uid].full_name if uid in evaluators_by_id else None)
                or (evaluators_by_id[uid].email if uid in evaluators_by_id else None)
                or f"User #{uid}",
            )
            for uid in evaluator_ids
        ],
    )


@router.get("/sessions", response_model=AdminSessionListResponse)
async def list_all_sessions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin_or_researcher)],
    user_id: Optional[int] = Query(None),
    case_id: Optional[int] = Query(None),
    start_date: Optional[UTCDateTime] = Query(None),
    end_date: Optional[UTCDateTime] = Query(None),
    state: Optional[str] = Query(None),
    patient_plugin: Optional[str] = Query(None),
    evaluator_plugin: Optional[str] = Query(None),
    evaluator_user_id: Optional[int] = Query(None),
    evaluation_status: Optional[str] = Query(
        None, description=f"One of {EVALUATION_STATUS_FILTER_VALUES}."
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """Filter sessions by any combination of user, case, date range, session state,
    patient/evaluator plugin, evaluation status, and evaluator (admin only).
    """
    from repositories.session_repo import SessionRepository

    if evaluation_status is not None and evaluation_status not in EVALUATION_STATUS_FILTER_VALUES:
        raise HTTPException(
            status_code=422,
            detail=f"evaluation_status must be one of {EVALUATION_STATUS_FILTER_VALUES}.",
        )

    session_repo = SessionRepository(db)

    sessions, total = session_repo.list_filtered(
        user_id=user_id,
        case_id=case_id,
        start_date=start_date,
        end_date=end_date,
        state=state,
        patient_plugin=patient_plugin,
        evaluator_plugin=evaluator_plugin,
        evaluator_user_id=evaluator_user_id,
        evaluation_status=evaluation_status,
        skip=skip,
        limit=limit,
    )

    user_ids = list({s.user_id for s in sessions})
    users_by_id: dict[int, User] = {}
    if user_ids:
        for u in db.query(User).filter(User.id.in_(user_ids)).all():
            users_by_id[u.id] = u

    # Real name/email are attached only for admins; a researcher sees the same
    # sessions and transcripts but with a pseudonymous participant reference instead
    # (see `_with_session_user_info`).
    redact_identity = current_user.role != "admin"

    # Convert to detailed responses
    session_service = SessionService(db)
    detailed_sessions = []
    for sess in sessions:
        detailed = await session_service.get_session(sess.id)
        detailed = _with_session_user_info(
            detailed, users_by_id.get(sess.user_id), redact_identity=redact_identity
        )
        detailed_sessions.append(detailed)

    return AdminSessionListResponse(
        sessions=detailed_sessions,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/sessions/{session_id}", response_model=AdminSessionDetail)
async def get_admin_session_detail(
    session_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin_or_researcher)],
):
    """Get transcript, feedback summary, and metrics timeline for a session.

    @remarks
    Admin and researcher roles both get the real transcript and feedback -- see
    `verify_session_access` for why researchers need real transcript content. Only
    the trainee's name/email are role-scoped: admins see them, researchers see a
    pseudonymous participant reference instead (`_with_session_user_info`).
    """
    session_service = SessionService(db)
    session_detail = await session_service.get_session(session_id)
    owner = db.query(User).filter(User.id == session_detail.user_id).first()
    session_detail = _with_session_user_info(
        session_detail, owner, redact_identity=current_user.role != "admin"
    )

    # Fetch feedback (no ownership restriction for admin)
    feedback_repo = FeedbackRepository(db)
    feedback_entity = feedback_repo.get_by_session(session_id)
    feedback_summary = None
    if feedback_entity:
        feedback_summary = AdminFeedbackSummary(
            empathy_score=feedback_entity.empathy_score,
            overall_score=feedback_entity.overall_score,
            strengths=feedback_entity.strengths,
            areas_for_improvement=feedback_entity.areas_for_improvement,
        )

    # Build metrics timeline
    metrics_timeline = []
    for turn in session_detail.turns:
        if turn.metrics_json:
            try:
                metrics = json.loads(turn.metrics_json.replace("'", '"'))
                metrics_timeline.append(
                    MetricsTimeline(
                        turn_number=turn.turn_number,
                        timestamp=turn.timestamp,
                        empathy_score=metrics.get("empathy", {}).get("empathy_score", 0),
                        question_type=metrics.get("question_type", "unknown"),
                        spikes_stage=turn.spikes_stage or "unknown",
                    )
                )
            except Exception:
                pass

    return AdminSessionDetail(
        session=session_detail,
        feedback=feedback_summary,
        metrics_timeline=metrics_timeline,
    )


ALLOWED_USER_OVERVIEW_SORT = frozenset({"last_active_desc", "avg_score_desc", "email_asc"})


@router.get("/users/overview", response_model=AdminUserOverviewResponse)
async def get_users_overview(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("last_active_desc"),
    role: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search email or full name (substring)"),
):
    """Paginated per-user session and feedback aggregates (admin only)."""
    if sort not in ALLOWED_USER_OVERVIEW_SORT:
        raise HTTPException(
            status_code=400,
            detail=f"sort must be one of: {', '.join(sorted(ALLOWED_USER_OVERVIEW_SORT))}",
        )
    user_repo = UserRepository(db)
    rows, total = user_repo.list_admin_overview(
        skip=skip,
        limit=limit,
        sort=sort,
        role=role,
        q=q,
    )
    return AdminUserOverviewResponse(
        users=[AdminUserOverviewRow(**r) for r in rows],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.patch("/users/{user_id}/role", response_model=AdminUserOverviewRow)
async def update_user_role(
    user_id: int,
    request: AdminUserRoleUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """Change a user's role (admin only). Role promotion is deliberately admin-only."""
    if request.role not in RoleScopes.get_all_scopes():
        raise HTTPException(
            status_code=422,
            detail=f"role must be one of: {', '.join(RoleScopes.get_all_scopes())}",
        )
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = request.role
    user_repo.update(user)

    rows, _ = user_repo.list_admin_overview(skip=0, limit=1, sort="email_asc", role=None, q=user.email)
    if rows:
        return AdminUserOverviewRow(**rows[0])
    # Fallback if aggregate lookup somehow misses (should not normally happen).
    return AdminUserOverviewRow(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        created_at=user.created_at,
        session_count=0,
        completed_session_count=0,
        last_session_at=None,
        average_overall_score=None,
        average_empathy_score=None,
    )


@router.get("/aggregates", response_model=AnalyticsDashboard)
async def get_aggregates(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """Get cohort/case aggregates (admin only)."""
    analytics_service = AnalyticsService(db)
    return await analytics_service.get_dashboard_analytics()


@router.get("/usage", response_model=UsageAdminResponse)
async def get_usage_dashboard(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
    days: int = Query(default=14, ge=1, le=90),
):
    """Today's global usage against the daily caps, plus a recent daily trend (admin only)."""
    from controllers.usage_controller import _resets_at_iso

    usage_service = UsageService(db)
    summary = usage_service.get_admin_summary()
    trend = usage_service.get_admin_trends(days=days)
    return UsageAdminResponse(
        categories=[
            CategoryUsageResponse(
                category=item.category,
                label=item.label,
                user_count=item.user_count,
                user_limit=item.user_limit,
                user_remaining=item.user_remaining,
                global_count=item.global_count,
                global_limit=item.global_limit,
                global_remaining=item.global_remaining,
            )
            for item in summary
        ],
        trend=[UsageTrendDay(**day) for day in trend],
        resets_at=_resets_at_iso(),
    )


@router.post("/cases", response_model=CaseResponse, status_code=201)
async def create_patient_case(
    case_data: CaseCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """Create patient case (admin only)."""
    case_service = CaseService(db)
    return await case_service.create_case(case_data)
