"""Session repository for database operations."""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.time import utc_now
from domain.entities.case import Case as CaseEntity
from domain.entities.research_annotation import (
    ResearchAnnotationSet,
    ResearchEvaluationRun,
)
from domain.entities.session import Session as SessionEntity

#: Query-param tokens for the `evaluation_status` filter, matching the Sessions-list
#: status chip's own labels/precedence exactly (see `ResearchAnnotationRepository
#: .get_evaluation_statuses_for_sessions` and the frontend's `evaluationChipFor`).
EVALUATION_STATUS_FILTER_VALUES = ("no_runs", "needs_review", "in_review", "locked")


def _evaluation_status_bucket(has_saved_runs: bool, latest_set) -> str:
    """Mirror the Sessions-list status chip's precedence exactly (see
    `ResearchAnnotationRepository.get_evaluation_statuses_for_sessions` and the
    frontend's `evaluationChipFor`): no_runs -> locked (latest set complete) ->
    in_review (draft/in_review) -> needs_review (runs exist, no set yet).
    """
    if not has_saved_runs:
        return "no_runs"
    if latest_set is not None and latest_set.status == "complete":
        return "locked"
    if latest_set is not None and latest_set.status in ("draft", "in_review"):
        return "in_review"
    return "needs_review"


class SessionRepository:
    """Repository for Session entity operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, session_id: int) -> Optional[SessionEntity]:
        """Get session by ID."""
        return self.db.query(SessionEntity).filter(SessionEntity.id == session_id).first()
    
    def get_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        state: str | None = None,
    ) -> list[SessionEntity]:
        """Get sessions for a user, optionally filtered by state."""
        q = self.db.query(SessionEntity).filter(SessionEntity.user_id == user_id)
        if state:
            q = q.filter(SessionEntity.state == state)
        return q.order_by(SessionEntity.started_at.desc()).offset(skip).limit(limit).all()

    def count_by_user_and_state(self, user_id: int, state: str) -> int:
        """Count sessions for a user in a given state."""
        return (
            self.db.query(SessionEntity)
            .filter(SessionEntity.user_id == user_id, SessionEntity.state == state)
            .count()
        )
    
    def get_by_case(
        self,
        case_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[SessionEntity]:
        """Get all sessions for a case."""
        return (
            self.db.query(SessionEntity)
            .filter(SessionEntity.case_id == case_id)
            .order_by(SessionEntity.started_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_active_for_user_case(self, user_id: int, case_id: int) -> Optional[SessionEntity]:
        """Get the most recent non-completed session for a user/case."""
        return (
            self.db.query(SessionEntity)
            .filter(
                SessionEntity.user_id == user_id,
                SessionEntity.case_id == case_id,
                SessionEntity.state != "completed",
            )
            .order_by(SessionEntity.started_at.desc())
            .first()
        )
    
    def get_all(self, skip: int = 0, limit: int = 100) -> list[SessionEntity]:
        """Get all sessions with pagination."""
        return (
            self.db.query(SessionEntity)
            .order_by(SessionEntity.started_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_filtered(
        self,
        *,
        user_id: int | None = None,
        case_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        state: str | None = None,
        patient_plugin: str | None = None,
        evaluator_plugin: str | None = None,
        evaluator_user_id: int | None = None,
        evaluation_status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[SessionEntity], int]:
        """List sessions matching any combination of filters, newest first.

        @remarks
        Replaces the admin sessions endpoint's old if/elif chain (which could only
        apply one of `user_id`/`case_id` at a time and silently ignored
        `start_date`/`end_date` entirely). All provided filters are ANDed together.
        Returns `(page, total_matching_count)` -- the count is computed from the
        same filtered query before `offset`/`limit` are applied, so pagination UI
        can tell how many total pages exist rather than only how many rows came
        back on this one page.

        `evaluator_user_id` (sessions with at least one annotation set reviewed by
        this user) is a plain SQL join/subquery. `evaluation_status` is different: the
        Sessions-list status chip is computed in Python by `ResearchAnnotationRepository
        .get_evaluation_statuses_for_sessions` (to reuse its exact precedence and avoid
        a second, drifting implementation in SQL), so filtering by it means evaluating
        every other filter first, computing statuses for that candidate set, then
        paginating the matches in Python. That's the only branch that can't paginate
        purely in SQL -- fine for this admin/research tool's session volumes, but worth
        knowing if it ever needs to scale further.
        """
        query = self.db.query(SessionEntity)
        if user_id is not None:
            query = query.filter(SessionEntity.user_id == user_id)
        if case_id is not None:
            query = query.filter(SessionEntity.case_id == case_id)
        if start_date is not None:
            query = query.filter(SessionEntity.started_at >= start_date)
        if end_date is not None:
            query = query.filter(SessionEntity.started_at <= end_date)
        if state is not None:
            query = query.filter(SessionEntity.state == state)
        if patient_plugin is not None:
            query = query.filter(SessionEntity.patient_model_plugin == patient_plugin)
        if evaluator_plugin is not None:
            query = query.filter(SessionEntity.evaluator_plugin == evaluator_plugin)
        if evaluator_user_id is not None:
            reviewed_session_ids = (
                self.db.query(ResearchEvaluationRun.source_session_id)
                .join(
                    ResearchAnnotationSet,
                    ResearchAnnotationSet.evaluation_run_id == ResearchEvaluationRun.id,
                )
                .filter(ResearchAnnotationSet.reviewer_user_id == evaluator_user_id)
                .distinct()
            )
            query = query.filter(SessionEntity.id.in_(reviewed_session_ids))

        if evaluation_status is not None:
            from repositories.research_annotation_repo import ResearchAnnotationRepository

            ordered_query = query.order_by(SessionEntity.started_at.desc())
            candidates = ordered_query.all()
            candidate_ids = [s.id for s in candidates]
            statuses = ResearchAnnotationRepository(
                self.db
            ).get_evaluation_statuses_for_sessions(candidate_ids)
            matching_ids = [
                sid
                for sid in candidate_ids
                if _evaluation_status_bucket(*statuses.get(sid, (False, None)))
                == evaluation_status
            ]
            total = len(matching_ids)
            page_ids = matching_ids[skip : skip + limit]
            sessions_by_id = {s.id: s for s in candidates}
            page = [sessions_by_id[sid] for sid in page_ids]
            return page, total

        total = query.count()
        page = (
            query.order_by(SessionEntity.started_at.desc()).offset(skip).limit(limit).all()
        )
        return page, total

    def distinct_patient_plugins(self) -> list[str]:
        """Distinct non-null `patient_model_plugin` values actually used by a session."""
        rows = (
            self.db.query(SessionEntity.patient_model_plugin)
            .filter(SessionEntity.patient_model_plugin.isnot(None))
            .distinct()
            .all()
        )
        return sorted({value for (value,) in rows if value})

    def distinct_evaluator_plugins(self) -> list[str]:
        """Distinct non-null `evaluator_plugin` values actually used by a session."""
        rows = (
            self.db.query(SessionEntity.evaluator_plugin)
            .filter(SessionEntity.evaluator_plugin.isnot(None))
            .distinct()
            .all()
        )
        return sorted({value for (value,) in rows if value})

    def distinct_evaluator_user_ids(self) -> list[int]:
        """Distinct `reviewer_user_id` values across all annotation sets -- the people
        who have evaluated at least one session, for the Sessions-list evaluator filter.
        """
        rows = (
            self.db.query(ResearchAnnotationSet.reviewer_user_id)
            .distinct()
            .all()
        )
        return sorted({value for (value,) in rows if value is not None})
    
    def create(self, session: SessionEntity) -> SessionEntity:
        """Create a new session."""
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session
    
    def update(self, session: SessionEntity) -> SessionEntity:
        """Update an existing session."""
        self.db.commit()
        self.db.refresh(session)
        return session
    
    def delete(self, session_id: int) -> bool:
        """Delete a session by ID."""
        session = self.get_by_id(session_id)
        if session:
            self.db.delete(session)
            self.db.commit()
            return True
        return False
    
    def count(self) -> int:
        """Count total sessions."""
        return self.db.query(SessionEntity).count()
    
    def count_by_state(self) -> dict[str, int]:
        """Count sessions by state."""
        results = (
            self.db.query(SessionEntity.state, func.count(SessionEntity.id))
            .group_by(SessionEntity.state)
            .all()
        )
        return {state: count for state, count in results}

    def count_by_case(self) -> dict[str, int]:
        """Count sessions per case, keyed by case title (joins cases for labels)."""
        results = (
            self.db.query(CaseEntity.title, func.count(SessionEntity.id))
            .select_from(SessionEntity)
            .join(CaseEntity, SessionEntity.case_id == CaseEntity.id)
            .group_by(CaseEntity.title)
            .all()
        )
        return {title: count for title, count in results}

    def get_average_duration(self) -> float:
        """Get average session duration in seconds."""
        result = self.db.query(func.avg(SessionEntity.duration_seconds)).scalar()
        return float(result) if result else 0.0
    
    def count_active_in_period(self, days: int = 30) -> int:
        """Count active sessions in the last N days."""
        cutoff_date = utc_now() - timedelta(days=days)
        return (
            self.db.query(SessionEntity)
            .filter(SessionEntity.started_at >= cutoff_date)
            .count()
        )

