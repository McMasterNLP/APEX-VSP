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
from plugins.registry import PluginRegistry
from domain.models.cases import CaseCreate, CaseResponse
from domain.models.sessions import SessionDetailResponse
from repositories.feedback_repo import FeedbackRepository
from repositories.user_repo import UserRepository
from services.analytics_service import AnalyticsService
from services.case_service import CaseService
from services.session_service import SessionService

router = APIRouter(prefix="/admin", tags=["admin"])


def _with_session_user_info(detail: SessionDetailResponse, row: User | None) -> SessionDetailResponse:
    """Attach email/name from the users table for admin UI (not stored on session)."""
    if not row:
        return detail
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


@router.get("/sessions", response_model=AdminSessionListResponse)
async def list_all_sessions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin_or_researcher)],
    user_id: Optional[int] = Query(None),
    case_id: Optional[int] = Query(None),
    start_date: Optional[UTCDateTime] = Query(None),
    end_date: Optional[UTCDateTime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """Filter sessions by user, case, date (admin only)."""
    from repositories.session_repo import SessionRepository
    
    session_repo = SessionRepository(db)
    
    # Get sessions with filters
    # Note: This is a simplified version - you'd add proper filtering in the repo
    if user_id:
        sessions = session_repo.get_by_user(user_id, skip, limit)
    elif case_id:
        sessions = session_repo.get_by_case(case_id, skip, limit)
    else:
        sessions = session_repo.get_all(skip, limit)

    user_ids = list({s.user_id for s in sessions})
    users_by_id: dict[int, User] = {}
    if user_ids:
        for u in db.query(User).filter(User.id.in_(user_ids)).all():
            users_by_id[u.id] = u

    # Convert to detailed responses
    session_service = SessionService(db)
    detailed_sessions = []
    for sess in sessions:
        detailed = await session_service.get_session(sess.id)
        detailed = _with_session_user_info(detailed, users_by_id.get(sess.user_id))
        detailed_sessions.append(detailed)

    return AdminSessionListResponse(
        sessions=detailed_sessions,
        total=len(sessions),
        skip=skip,
        limit=limit,
    )


@router.get("/sessions/{session_id}", response_model=AdminSessionDetail)
async def get_admin_session_detail(
    session_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin_or_researcher)],
):
    """Get transcript, feedback summary, and metrics timeline for a session (admin only)."""
    session_service = SessionService(db)
    session_detail = await session_service.get_session(session_id)
    owner = db.query(User).filter(User.id == session_detail.user_id).first()
    session_detail = _with_session_user_info(session_detail, owner)

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


@router.post("/cases", response_model=CaseResponse, status_code=201)
async def create_patient_case(
    case_data: CaseCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """Create patient case (admin only)."""
    case_service = CaseService(db)
    return await case_service.create_case(case_data)
