"""Pydantic schemas for request/response models."""

from domain.models.admin import (
    AnalyticsDashboard,
    PerformanceStats,
    ResearchExportRequest,
    ResearchExportResponse,
    SessionStats,
    UserStats,
)
from domain.models.auth import (
    UserResponse,
    UserUpdate,
)
from domain.models.cases import (
    CaseCreate,
    CaseListResponse,
    CaseResponse,
    CaseUpdate,
)
from domain.models.evaluator_comparison import CanonicalTranscriptTurn, EvaluatorProvenance
from domain.models.scoring import ComputedFeedback
from domain.models.sessions import (
    FeedbackResponse,
    SessionCreate,
    SessionDetailResponse,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
    TurnCreate,
    TurnResponse,
    WebSocketMessage,
)

__all__ = [
    # Auth
    "UserUpdate",
    "UserResponse",
    # Cases
    "CaseCreate",
    "CaseUpdate",
    "CaseResponse",
    "CaseListResponse",
    # Sessions
    "SessionCreate",
    "SessionUpdate",
    "SessionResponse",
    "SessionDetailResponse",
    "SessionListResponse",
    "TurnCreate",
    "TurnResponse",
    "FeedbackResponse",
    "ComputedFeedback",
    "CanonicalTranscriptTurn",
    "EvaluatorProvenance",
    "WebSocketMessage",
    # Admin
    "UserStats",
    "SessionStats",
    "PerformanceStats",
    "AnalyticsDashboard",
    "ResearchExportRequest",
    "ResearchExportResponse",
]
