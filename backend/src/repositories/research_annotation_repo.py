"""Repository queries for durable research runs and annotation records."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from domain.entities.research_annotation import (
    ResearchAnnotationSet,
    ResearchAnnotationTransition,
    ResearchEvaluationRun,
    ResearchReviewDecisionRevision,
)


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

    def add_annotation_set(self, annotation_set: ResearchAnnotationSet) -> ResearchAnnotationSet:
        self.db.add(annotation_set)
        self.db.flush()
        return annotation_set

    def get_annotation_set(
        self,
        annotation_set_uuid: UUID,
        *,
        for_update: bool = False,
    ) -> ResearchAnnotationSet | None:
        query = self.db.query(ResearchAnnotationSet).filter(
            ResearchAnnotationSet.id == annotation_set_uuid
        )
        if for_update:
            query = query.with_for_update()
        return query.first()

    def find_annotation_set(
        self,
        *,
        evaluation_run_id: UUID,
        reviewer_user_id: int,
        guideline_identifier: str,
        guideline_version: str,
    ) -> ResearchAnnotationSet | None:
        return (
            self.db.query(ResearchAnnotationSet)
            .filter(
                ResearchAnnotationSet.evaluation_run_id == evaluation_run_id,
                ResearchAnnotationSet.reviewer_user_id == reviewer_user_id,
                ResearchAnnotationSet.guideline_identifier == guideline_identifier,
                ResearchAnnotationSet.guideline_version == guideline_version,
            )
            .first()
        )

    def add_decision_revision(
        self,
        decision: ResearchReviewDecisionRevision,
    ) -> ResearchReviewDecisionRevision:
        self.db.add(decision)
        self.db.flush()
        return decision

    def list_decision_revisions(
        self,
        annotation_set_id: UUID,
        *,
        prediction_id: str | None = None,
    ) -> list[ResearchReviewDecisionRevision]:
        query = self.db.query(ResearchReviewDecisionRevision).filter(
            ResearchReviewDecisionRevision.annotation_set_id == annotation_set_id
        )
        if prediction_id is not None:
            query = query.filter(ResearchReviewDecisionRevision.prediction_id == prediction_id)
        return query.order_by(
            ResearchReviewDecisionRevision.prediction_id.asc(),
            ResearchReviewDecisionRevision.revision_number.asc(),
        ).all()

    def add_transition(
        self,
        transition: ResearchAnnotationTransition,
    ) -> ResearchAnnotationTransition:
        self.db.add(transition)
        self.db.flush()
        return transition

    def list_transitions(
        self,
        annotation_set_id: UUID,
    ) -> list[ResearchAnnotationTransition]:
        return (
            self.db.query(ResearchAnnotationTransition)
            .filter(ResearchAnnotationTransition.annotation_set_id == annotation_set_id)
            .order_by(ResearchAnnotationTransition.set_revision.asc())
            .all()
        )
