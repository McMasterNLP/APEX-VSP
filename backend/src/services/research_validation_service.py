"""Item 3A orchestration: score a saved evaluator run against a human reference.

@remarks
Gate for "annotation set must be finalized enough to validate": this service
requires `annotation_set.status == "complete"` (equivalently `.locked`). This
is a deliberate choice, stricter than merely `progress.unreviewed == 0`: the
existing `complete()` lifecycle action already blocks completion while
`coverage_level == "not_assessed"`, so requiring `status == "complete"` also
guarantees coverage was explicitly declared -- exactly the kind of finality a
persisted, immutable validation metric should require before it exists at
all.

The evaluator's own (unreviewed) `ResearchProjection` for the run being
validated is read directly off `EvaluationRunRecord.envelope.projection` --
`ResearchEvaluationEnvelope.projection: ResearchProjection` already holds
exactly this (see `domain/models/research_evaluation.py`); this is also how
`eligible_prediction_inventory` (Item 2A's own policy module) sources the
review inventory, so it is a well-trodden path, not a new interpretation.

Eligibility is reused via `AnnotationSetRecord.validation_eligibility`, which
`ResearchAnnotationService._validation_eligibility` already computes fresh on
every read -- rather than re-invoking that private static method a second
time here, this service simply reads the already-materialized field off the
fetched annotation-set record.
"""

from __future__ import annotations

import json
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from core.time import utc_now
from domain.entities.research_annotation import ResearchValidationRun
from domain.entities.user import User
from domain.models.research_annotation import AnnotationSetRecord
from domain.models.research_evaluation import (
    ResearchProjection,
    validate_projection_against_transcript,
)
from domain.models.research_validation import (
    SPAN_CLASSIFICATION_METRIC_IMPLEMENTATION_VERSION,
    SpanClassificationMetrics,
    ValidationRunCreateRequest,
    ValidationRunRecord,
    ValidationRunResult,
)
from repositories.research_annotation_repo import ResearchAnnotationRepository
from services.research_annotation_service import (
    ResearchAnnotationService,
    ResearchAnnotationServiceError,
)
from services.research_evaluation_run_service import (
    ResearchEvaluationRunService,
    ResearchEvaluationRunServiceError,
    pseudonymous_reviewer_reference,
)
from services.research_validation.metrics import compute_span_classification_metrics
from services.research_validation.registry import MATCHING_POLICY_REGISTRY


class ResearchValidationServiceError(ValueError):
    """Allowlisted validation-run error safe for API status mapping."""

    def __init__(
        self,
        category: Literal[
            "evaluation_run_not_found",
            "annotation_set_not_found",
            "annotation_set_not_complete",
            "transcript_mismatch",
            "unknown_matching_policy",
            "invalid_projection",
            "validation_run_not_found",
            "persistence_failed",
        ],
        message: str,
    ):
        self.category = category
        super().__init__(message)


class ResearchValidationService:
    """Score one saved evaluator run against one completed annotation set's reference."""

    def __init__(
        self,
        db: Session,
        *,
        repository: ResearchAnnotationRepository | None = None,
        run_service: ResearchEvaluationRunService | None = None,
        annotation_service: ResearchAnnotationService | None = None,
    ):
        self.db = db
        self.repository = repository or ResearchAnnotationRepository(db)
        self.run_service = run_service or ResearchEvaluationRunService(db)
        self.annotation_service = annotation_service or ResearchAnnotationService(
            db, repository=self.repository, run_service=self.run_service
        )

    def create_validation_run(
        self,
        request: ValidationRunCreateRequest,
        creator: User,
    ) -> ValidationRunRecord:
        try:
            run = self.run_service.get_run(request.evaluation_run_uuid)
        except ResearchEvaluationRunServiceError as error:
            raise ResearchValidationServiceError(
                "evaluation_run_not_found",
                "The evaluation run being validated was not found.",
            ) from error
        try:
            annotation_set = self.annotation_service.get_annotation_set(
                request.annotation_set_uuid
            )
        except ResearchAnnotationServiceError as error:
            raise ResearchValidationServiceError(
                "annotation_set_not_found",
                "The reference annotation set was not found.",
            ) from error

        if annotation_set.status != "complete":
            raise ResearchValidationServiceError(
                "annotation_set_not_complete",
                "The reference annotation set must be complete (coverage declared and "
                "every eligible prediction reviewed) before it can back a validation run.",
            )

        run_transcript_hash = run.envelope.transcript.canonical_transcript_hash
        if run_transcript_hash != annotation_set.transcript_hash:
            raise ResearchValidationServiceError(
                "transcript_mismatch",
                "The evaluation run being validated and the reference annotation set were "
                "computed against different transcripts; validation requires a shared "
                "transcript_hash.",
            )

        try:
            policy = MATCHING_POLICY_REGISTRY.get(request.matching_policy_identifier)
        except ValueError as error:
            raise ResearchValidationServiceError("unknown_matching_policy", str(error)) from error

        evaluator_projection: ResearchProjection = run.envelope.projection
        reference_projection: ResearchProjection = annotation_set.resolved_projection
        try:
            validate_projection_against_transcript(evaluator_projection, run.transcript_snapshot)
            validate_projection_against_transcript(reference_projection, run.transcript_snapshot)
        except ValueError as error:
            raise ResearchValidationServiceError(
                "invalid_projection",
                f"A projection failed transcript validation and cannot be scored: {error}",
            ) from error

        eligibility = annotation_set.validation_eligibility
        outcomes = policy.match(evaluator_projection.spans, reference_projection.spans)
        span_classification: SpanClassificationMetrics = compute_span_classification_metrics(
            outcomes,
            eligibility,
            metric_implementation_version=SPAN_CLASSIFICATION_METRIC_IMPLEMENTATION_VERSION,
            matching_policy_identifier=policy.policy_identifier,
            matching_policy_version=policy.version,
        )
        results = ValidationRunResult(
            coverage_level=annotation_set.coverage_level,
            eligibility=eligibility,
            span_classification=span_classification,
        )
        warnings = _build_warnings(annotation_set, evaluator_projection)

        now = utc_now()
        entity = ResearchValidationRun(
            evaluation_run_id=request.evaluation_run_uuid,
            annotation_set_id=request.annotation_set_uuid,
            annotation_set_revision_at_validation=annotation_set.revision,
            transcript_hash=annotation_set.transcript_hash,
            evaluator_identifier=run.envelope.evaluator.identifier,
            evaluator_version=run.envelope.evaluator.version,
            matching_policy_identifier=policy.policy_identifier,
            matching_policy_version=policy.version,
            metric_implementation_version=SPAN_CLASSIFICATION_METRIC_IMPLEMENTATION_VERSION,
            coverage_level=annotation_set.coverage_level,
            results_json=results.model_dump_json(),
            warnings_json=_dump_warnings(warnings),
            created_by_user_id=creator.id,
            created_at=now,
        )
        try:
            self.repository.add_validation_run(entity)
            self.db.commit()
            self.db.refresh(entity)
        except Exception as error:
            self.db.rollback()
            raise ResearchValidationServiceError(
                "persistence_failed", "The validation run could not be saved."
            ) from error

        return self._record(entity)

    def get_validation_run(self, validation_run_uuid: UUID) -> ValidationRunRecord:
        entity = self.repository.get_validation_run(validation_run_uuid)
        if entity is None:
            raise ResearchValidationServiceError(
                "validation_run_not_found", "The requested validation run was not found."
            )
        return self._record(entity)

    @staticmethod
    def _record(entity: ResearchValidationRun) -> ValidationRunRecord:
        return ValidationRunRecord(
            validation_run_uuid=entity.id,
            evaluation_run_uuid=entity.evaluation_run_id,
            annotation_set_uuid=entity.annotation_set_id,
            annotation_set_revision_at_validation=entity.annotation_set_revision_at_validation,
            transcript_hash=entity.transcript_hash,
            evaluator_identifier=entity.evaluator_identifier,
            evaluator_version=entity.evaluator_version,
            matching_policy_identifier=entity.matching_policy_identifier,
            matching_policy_version=entity.matching_policy_version,
            metric_implementation_version=entity.metric_implementation_version,
            coverage_level=entity.coverage_level,
            results=ValidationRunResult.model_validate_json(entity.results_json),
            warnings=tuple(json.loads(entity.warnings_json)),
            created_by_reference=pseudonymous_reviewer_reference(entity.created_by_user_id),
            created_at=entity.created_at,
        )


def _build_warnings(
    annotation_set: AnnotationSetRecord,
    evaluator_projection: ResearchProjection,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if (
        evaluator_projection.turn_labels
        or evaluator_projection.relations
        or evaluator_projection.dimension_ratings
        or evaluator_projection.findings
    ):
        warnings.append(
            "Turn-label, relation, dimension-rating, and finding projections are out of "
            "scope for this validation run's span-classification metric family; only span "
            "annotations were scored."
        )
    if not annotation_set.transcript_matches_current:
        warnings.append(
            "The annotation set's transcript no longer matches the source session's current "
            "transcript; the validation run still scored the snapshot both projections share."
        )
    return tuple(warnings)


def _dump_warnings(warnings: tuple[str, ...]) -> str:
    return json.dumps(list(warnings), ensure_ascii=False, separators=(",", ":"))
