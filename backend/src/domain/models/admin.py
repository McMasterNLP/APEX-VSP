"""Admin and analytics schemas."""

from typing import Optional

from pydantic import BaseModel, Field

from core.time import UTCDateTime


class UserStats(BaseModel):
    """User statistics schema."""
    
    total_users: int
    users_by_role: dict[str, int]
    active_users_last_30_days: int


class SessionStats(BaseModel):
    """Session statistics schema."""
    
    total_sessions: int
    completed_sessions: int
    active_sessions: int
    average_duration_seconds: float
    sessions_by_case: dict[str, int]


class MonthScoreAverage(BaseModel):
    """Average overall score for a calendar month (YYYY-MM)."""

    month: str
    score: float


class PerformanceStats(BaseModel):
    """Performance statistics schema."""

    average_empathy_score: float
    average_communication_score: float
    average_spikes_completion: float
    average_overall_score: float
    average_score_by_month: list[MonthScoreAverage] = Field(default_factory=list)


class CaseStats(BaseModel):
    """Case statistics summary."""

    total_cases: int
    cases_by_category: dict[str, int]


class AnalyticsDashboard(BaseModel):
    """Analytics dashboard schema."""

    user_stats: UserStats
    session_stats: SessionStats
    performance_stats: PerformanceStats
    case_stats: CaseStats
    generated_at: UTCDateTime


class ResearchExportRequest(BaseModel):
    """Research export request schema."""
    
    include_turns: bool = True
    include_feedback: bool = True
    anonymize: bool = True
    start_date: Optional[UTCDateTime] = None
    end_date: Optional[UTCDateTime] = None
    case_ids: Optional[list[int]] = None


class ResearchExportResponse(BaseModel):
    """Research export response schema."""
    
    export_id: str
    download_url: str
    generated_at: UTCDateTime
    record_count: int


class ResearchSessionSummary(BaseModel):
    """Anonymized per-session summary for research dashboard."""

    session_id: str
    case_id: int
    case_name: Optional[str] = None
    patient_model_plugin: Optional[str] = None
    evaluator_plugin: Optional[str] = None
    metrics_plugins: Optional[str] = None
    duration_seconds: Optional[int] = None
    state: str
    spikes_stage: Optional[str] = None
    empathy_score: Optional[float] = None
    communication_score: Optional[float] = None
    clinical_score: Optional[float] = None
    timestamp: Optional[UTCDateTime] = None


class ResearchSessionsEnvelope(BaseModel):
    """Envelope for paginated anonymized research sessions."""

    sessions: list[ResearchSessionSummary]
    total: int
    skip: int
    limit: int


class AdminUserOverviewRow(BaseModel):
    """Per-user aggregates for the admin user management table."""

    id: int
    email: str
    full_name: Optional[str] = None
    role: str
    created_at: UTCDateTime
    session_count: int
    completed_session_count: int
    last_session_at: Optional[UTCDateTime] = None
    average_overall_score: Optional[float] = None
    average_empathy_score: Optional[float] = None


class AdminUserOverviewResponse(BaseModel):
    """Paginated user overview for admin."""

    users: list[AdminUserOverviewRow]
    total: int
    skip: int
    limit: int


class AdminUserRoleUpdateRequest(BaseModel):
    """Request body for an admin changing another user's role."""

    role: str

