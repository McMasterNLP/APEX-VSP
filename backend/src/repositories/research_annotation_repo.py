"""Repository queries for durable research runs and annotation records."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from domain.entities.research_annotation import ResearchEvaluationRun


class ResearchAnnotationRepository:
    """Persistence access that leaves transaction control to the service."""

    def __init__(self, db: Session):
        self.db = db

    def add_evaluation_run(self, run: ResearchEvaluationRun) -> ResearchEvaluationRun:
        self.db.add(run)
        self.db.flush()
        return run

    def get_evaluation_run(self, run_uuid: UUID) -> ResearchEvaluationRun | None:
        return (
            self.db.query(ResearchEvaluationRun)
            .filter(ResearchEvaluationRun.id == run_uuid)
            .first()
        )

    def list_evaluation_runs_for_session(
        self,
        session_id: int,
    ) -> list[ResearchEvaluationRun]:
        return (
            self.db.query(ResearchEvaluationRun)
            .filter(ResearchEvaluationRun.source_session_id == session_id)
            .order_by(ResearchEvaluationRun.created_at.desc())
            .all()
        )
