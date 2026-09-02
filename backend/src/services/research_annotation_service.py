"""Reviewer-specific annotation lifecycle and append-only decision service."""

from __future__ import annotations

import json
from typing import Literal
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.time import utc_now
from domain.entities.research_annotation import (
    ResearchAnnotationSet,
    ResearchAnnotationTransition,
    ResearchReviewDecisionRevision,
)
from domain.entities.user import User
from domain.models.research_annotation import (
    AnnotationPolicyDescriptor,
    AnnotationSetCompleteRequest,
    AnnotationSetCreateRequest,
    AnnotationSetRecord,
    AnnotationSetReopenRequest,
    AnnotationTransitionRecord,
    DecisionRevisionRecord,
    DimensionRatingCorrection,
    LabelPolicy,
    ReviewDecisionWriteRequest,
    ReviewProgress,
    ReviewablePrediction,
    SpanCorrection,
    TurnLabelCorrection,
    TypedCorrection,
)
from domain.models.research_evaluation import (
    DimensionRating,
    ProjectedRelation,
    ResearchProjection,
    SpanAnnotation,
    TurnLabel,
)
from repositories.research_annotation_repo import ResearchAnnotationRepository
from services.research_annotation_policy import (
    AnnotationPolicyError,
    eligible_prediction_inventory,
    policy_for_envelope,
    validate_requested_guideline,
)
from services.research_evaluation_run_service import (
    ResearchEvaluationRunService,
    ResearchEvaluationRunServiceError,
    pseudonymous_reviewer_reference,
)

_INVENTORY_ADAPTER = TypeAdapter(tuple[ReviewablePrediction, ...])
_CORRECTION_ADAPTER = TypeAdapter(TypedCorrection)


class ResearchAnnotationServiceError(ValueError):
    """Allowlisted annotation error with optional sanitized conflict state."""

    def __init__(
        self,
        category: Literal[
            "annotation_set_not_found",
            "annotation_set_forbidden",
            "annotation_set_locked",
            "no_reviewable_predictions",
            "invalid_guideline",
            "invalid_prediction",
            "invalid_decision",
            "invalid_correction",
            "revision_conflict",
            "completion_blocked",
            "invalid_transition",
            "persistence_failed",
        ],
        message: str,
        *,
        current_set_revision: int | None = None,
        current_decision_revision: int | None = None,
    ):
        self.category = category
        self.current_set_revision = current_set_revision
        self.current_decision_revision = current_decision_revision
        super().__init__(message)


class ResearchAnnotationService:
    """Create review sets and mutate them only through auditable revisions."""

    def __init__(
        self,
        db: Session,
        *,
        repository: ResearchAnnotationRepository | None = None,
        run_service: ResearchEvaluationRunService | None = None,
    ):
        self.db = db
        self.repository = repository or ResearchAnnotationRepository(db)
        self.run_service = run_service or ResearchEvaluationRunService(db)

    def create_annotation_set(
        self,
        run_uuid: UUID,
        request: AnnotationSetCreateRequest,
        reviewer: User,
    ) -> AnnotationSetRecord:
        try:
            run = self.run_service.get_run(run_uuid)
        except ResearchEvaluationRunServiceError as error:
            raise ResearchAnnotationServiceError(
                "annotation_set_not_found", "The saved evaluation run was not found."
            ) from error
        policy = run.annotation_policy
        try:
            validate_requested_guideline(
                policy,
                request.guideline_identifier,
                request.guideline_version,
            )
        except AnnotationPolicyError as error:
            raise ResearchAnnotationServiceError("invalid_guideline", str(error)) from error

        existing = self.repository.find_annotation_set(
            evaluation_run_id=run_uuid,
            reviewer_user_id=reviewer.id,
            guideline_identifier=request.guideline_identifier,
            guideline_version=request.guideline_version,
        )
        if existing is not None:
            return self._record(existing)

        inventory = eligible_prediction_inventory(run.envelope, policy)
        if not inventory:
            raise ResearchAnnotationServiceError(
                "no_reviewable_predictions",
                "This saved run has no predictions eligible for Item 2A review.",
            )
        now = utc_now()
        entity = ResearchAnnotationSet(
            evaluation_run_id=run_uuid,
            transcript_hash=run.envelope.transcript.canonical_transcript_hash,
            framework_identifier=run.envelope.framework.identifier,
            framework_version=run.envelope.framework.version,
            annotation_policy_identifier=policy.policy_identifier,
            annotation_policy_version=policy.policy_version,
            guideline_identifier=policy.guideline_identifier,
            guideline_version=policy.guideline_version,
            reviewer_user_id=reviewer.id,
            status="draft",
            revision=0,
            eligible_predictions_json=json.dumps(
                [item.model_dump(mode="json") for item in inventory],
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            set_note=request.set_note,
            created_at=now,
            updated_at=now,
        )
        try:
            self.repository.add_annotation_set(entity)
            self.db.commit()
            self.db.refresh(entity)
        except IntegrityError:
            self.db.rollback()
            concurrent = self.repository.find_annotation_set(
                evaluation_run_id=run_uuid,
                reviewer_user_id=reviewer.id,
                guideline_identifier=request.guideline_identifier,
                guideline_version=request.guideline_version,
            )
            if concurrent is not None:
                return self._record(concurrent)
            raise ResearchAnnotationServiceError(
                "persistence_failed", "The annotation set could not be created."
            )
        except Exception as error:
            self.db.rollback()
            raise ResearchAnnotationServiceError(
                "persistence_failed", "The annotation set could not be created."
            ) from error
        return self._record(entity)

    def get_annotation_set(self, annotation_set_uuid: UUID) -> AnnotationSetRecord:
        entity = self.repository.get_annotation_set(annotation_set_uuid)
        if entity is None:
            raise ResearchAnnotationServiceError(
                "annotation_set_not_found", "The requested annotation set was not found."
            )
        return self._record(entity)

    def record_decision(
        self,
        annotation_set_uuid: UUID,
        prediction_id: str,
        request: ReviewDecisionWriteRequest,
        reviewer: User,
    ) -> AnnotationSetRecord:
        annotation_set = self._locked_set(annotation_set_uuid)
        self._require_reviewer(annotation_set, reviewer)
        if annotation_set.status == "complete":
            raise ResearchAnnotationServiceError(
                "annotation_set_locked", "Complete annotation sets are locked."
            )
        inventory = self._inventory(annotation_set)
        prediction = next(
            (item for item in inventory if item.prediction_id == prediction_id), None
        )
        if prediction is None:
            raise ResearchAnnotationServiceError(
                "invalid_prediction", "The prediction is not in this annotation set."
            )
        current = self.repository.list_decision_revisions(
            annotation_set.id, prediction_id=prediction_id
        )
        current_revision = current[-1] if current else None
        self._check_revisions(annotation_set, current_revision, request)

        run = self.run_service.get_run(annotation_set.evaluation_run_id)
        policy = policy_for_envelope(run.envelope)
        self._validate_decision(
            prediction,
            request,
            policy,
            {turn.turn_number for turn in run.transcript_snapshot},
        )

        revision_number = 1 if current_revision is None else current_revision.revision_number + 1
        decision = ResearchReviewDecisionRevision(
            annotation_set_id=annotation_set.id,
            prediction_id=prediction.prediction_id,
            prediction_snapshot_json=prediction.original_prediction.model_dump_json(),
            source_reference_json=prediction.original_prediction.source_reference.model_dump_json(),
            projection_type=prediction.projection_type,
            revision_number=revision_number,
            decision=request.decision,
            correction_json=(
                request.correction.model_dump_json() if request.correction is not None else None
            ),
            reviewer_note=request.reviewer_note,
            reviewer_user_id=reviewer.id,
            supersedes_id=current_revision.id if current_revision is not None else None,
            created_at=utc_now(),
        )
        annotation_set.revision += 1
        annotation_set.updated_at = decision.created_at
        if annotation_set.status == "draft":
            annotation_set.status = "in_review"
        try:
            self.repository.add_decision_revision(decision)
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            latest_set = self.repository.get_annotation_set(annotation_set_uuid)
            latest_decisions = self.repository.list_decision_revisions(
                annotation_set_uuid, prediction_id=prediction_id
            )
            raise ResearchAnnotationServiceError(
                "revision_conflict",
                "Newer review data exists; refresh before saving again.",
                current_set_revision=latest_set.revision if latest_set else None,
                current_decision_revision=(
                    latest_decisions[-1].revision_number if latest_decisions else None
                ),
            ) from error
        except Exception as error:
            self.db.rollback()
            raise ResearchAnnotationServiceError(
                "persistence_failed", "The review decision could not be saved."
            ) from error
        return self.get_annotation_set(annotation_set_uuid)

    def complete(
        self,
        annotation_set_uuid: UUID,
        request: AnnotationSetCompleteRequest,
        reviewer: User,
    ) -> AnnotationSetRecord:
        annotation_set = self._locked_set(annotation_set_uuid)
        self._require_reviewer(annotation_set, reviewer)
        if annotation_set.status == "complete":
            raise ResearchAnnotationServiceError(
                "annotation_set_locked", "The annotation set is already complete and locked."
            )
        self._check_set_revision(annotation_set, request.expected_set_revision)
        inventory = self._inventory(annotation_set)
        decisions = self._effective_decision_entities(annotation_set.id)
        missing = [item for item in inventory if item.prediction_id not in decisions]
        if missing:
            raise ResearchAnnotationServiceError(
                "completion_blocked",
                f"Review {len(missing)} remaining prediction(s) before completion.",
            )
        self._validate_resolved_relations(inventory, decisions)

        now = utc_now()
        from_status = annotation_set.status
        annotation_set.status = "complete"
        annotation_set.revision += 1
        annotation_set.updated_at = now
        annotation_set.completed_at = now
        annotation_set.locked_at = now
        transition = ResearchAnnotationTransition(
            annotation_set_id=annotation_set.id,
            from_status=from_status,
            to_status="complete",
            set_revision=annotation_set.revision,
            actor_user_id=reviewer.id,
            created_at=now,
        )
        return self._save_transition(annotation_set, transition)

    def reopen(
        self,
        annotation_set_uuid: UUID,
        request: AnnotationSetReopenRequest,
        actor: User,
    ) -> AnnotationSetRecord:
        annotation_set = self._locked_set(annotation_set_uuid)
        if annotation_set.status != "complete":
            raise ResearchAnnotationServiceError(
                "invalid_transition", "Only a complete annotation set can be reopened."
            )
        self._check_set_revision(annotation_set, request.expected_set_revision)
        now = utc_now()
        annotation_set.status = "in_review"
        annotation_set.revision += 1
        annotation_set.updated_at = now
        annotation_set.locked_at = None
        annotation_set.reopened_at = now
        transition = ResearchAnnotationTransition(
            annotation_set_id=annotation_set.id,
            from_status="complete",
            to_status="in_review",
            set_revision=annotation_set.revision,
            reason=request.reason,
            actor_user_id=actor.id,
            created_at=now,
        )
        return self._save_transition(annotation_set, transition)

    def _save_transition(
        self,
        annotation_set: ResearchAnnotationSet,
        transition: ResearchAnnotationTransition,
    ) -> AnnotationSetRecord:
        try:
            self.repository.add_transition(transition)
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            current = self.repository.get_annotation_set(annotation_set.id)
            raise ResearchAnnotationServiceError(
                "revision_conflict",
                "Newer lifecycle data exists; refresh before trying again.",
                current_set_revision=current.revision if current else None,
            ) from error
        except Exception as error:
            self.db.rollback()
            raise ResearchAnnotationServiceError(
                "persistence_failed", "The annotation-set transition could not be saved."
            ) from error
        return self.get_annotation_set(annotation_set.id)

    def _locked_set(self, annotation_set_uuid: UUID) -> ResearchAnnotationSet:
        entity = self.repository.get_annotation_set(annotation_set_uuid, for_update=True)
        if entity is None:
            raise ResearchAnnotationServiceError(
                "annotation_set_not_found", "The requested annotation set was not found."
            )
        return entity

    @staticmethod
    def _require_reviewer(annotation_set: ResearchAnnotationSet, reviewer: User) -> None:
        if annotation_set.reviewer_user_id != reviewer.id:
            raise ResearchAnnotationServiceError(
                "annotation_set_forbidden",
                "Only the annotation-set reviewer can record or complete decisions.",
            )

    def _check_revisions(
        self,
        annotation_set: ResearchAnnotationSet,
        current: ResearchReviewDecisionRevision | None,
        request: ReviewDecisionWriteRequest,
    ) -> None:
        current_decision_revision = current.revision_number if current else None
        if (
            request.expected_set_revision != annotation_set.revision
            or request.expected_decision_revision != current_decision_revision
        ):
            raise ResearchAnnotationServiceError(
                "revision_conflict",
                "Newer review data exists; refresh before saving again.",
                current_set_revision=annotation_set.revision,
                current_decision_revision=current_decision_revision,
            )

    @staticmethod
    def _check_set_revision(annotation_set: ResearchAnnotationSet, expected: int) -> None:
        if expected != annotation_set.revision:
            raise ResearchAnnotationServiceError(
                "revision_conflict",
                "Newer review data exists; refresh before changing lifecycle state.",
                current_set_revision=annotation_set.revision,
            )

    def _validate_decision(
        self,
        prediction: ReviewablePrediction,
        request: ReviewDecisionWriteRequest,
        policy: AnnotationPolicyDescriptor,
        transcript_turns: set[int],
    ) -> None:
        operations = prediction.allowed_operations
        if request.decision == "confirmed":
            if not operations.confirm:
                self._invalid_decision()
            return
        if request.decision == "rejected":
            if not operations.reject:
                self._invalid_decision()
            return
        if isinstance(prediction.original_prediction, (SpanAnnotation, TurnLabel)):
            self._validate_label_correction(prediction, request, policy)
            return
        if isinstance(prediction.original_prediction, DimensionRating):
            self._validate_rating_correction(
                prediction, request, policy, transcript_turns
            )
            return
        raise ResearchAnnotationServiceError(
            "invalid_correction", "This projection type cannot be corrected in Item 2A."
        )

    @staticmethod
    def _invalid_decision() -> None:
        raise ResearchAnnotationServiceError(
            "invalid_decision", "The annotation policy does not allow this decision."
        )

    def _validate_label_correction(
        self,
        prediction: ReviewablePrediction,
        request: ReviewDecisionWriteRequest,
        policy: AnnotationPolicyDescriptor,
    ) -> None:
        original = prediction.original_prediction
        correction = request.correction
        expected_type = (
            SpanCorrection if isinstance(original, SpanAnnotation) else TurnLabelCorrection
        )
        if request.decision != "corrected" or not isinstance(correction, expected_type):
            raise ResearchAnnotationServiceError(
                "invalid_correction", "The correction type does not match the prediction."
            )
        label_policy = next(
            item for item in policy.label_policies if item.projection_type == prediction.projection_type
        )
        self._validate_label_policy(label_policy, correction)
        label_changed = correction.corrected_label != original.label
        dimension_changed = correction.corrected_dimension != original.dimension
        if not label_changed and not dimension_changed:
            raise ResearchAnnotationServiceError(
                "invalid_correction", "A correction must change an allowed value."
            )
        if label_changed and not prediction.allowed_operations.change_label:
            self._invalid_decision()
        if dimension_changed and not prediction.allowed_operations.change_dimension:
            self._invalid_decision()
        if isinstance(original, SpanAnnotation):
            if correction.corrected_label == "empathic_opportunity":
                if correction.corrected_dimension is None:
                    raise ResearchAnnotationServiceError(
                        "invalid_correction",
                        "Empathic opportunities require an allowed dimension.",
                    )
            elif correction.corrected_dimension is not None:
                raise ResearchAnnotationServiceError(
                    "invalid_correction",
                    "Only empathic opportunities carry an AFCE dimension.",
                )

    @staticmethod
    def _validate_label_policy(
        policy: LabelPolicy,
        correction: SpanCorrection | TurnLabelCorrection,
    ) -> None:
        if correction.corrected_label not in policy.allowed_labels:
            raise ResearchAnnotationServiceError(
                "invalid_correction", "The corrected label is not allowed by the policy."
            )
        dimension = correction.corrected_dimension
        if dimension is None and not policy.allow_null_dimension:
            raise ResearchAnnotationServiceError(
                "invalid_correction", "The correction requires a dimension."
            )
        if dimension is not None and dimension not in policy.allowed_dimensions:
            raise ResearchAnnotationServiceError(
                "invalid_correction", "The corrected dimension is not allowed by the policy."
            )

    def _validate_rating_correction(
        self,
        prediction: ReviewablePrediction,
        request: ReviewDecisionWriteRequest,
        policy: AnnotationPolicyDescriptor,
        transcript_turns: set[int],
    ) -> None:
        original = prediction.original_prediction
        correction = request.correction
        if not isinstance(original, DimensionRating) or not isinstance(
            correction, DimensionRatingCorrection
        ):
            raise ResearchAnnotationServiceError(
                "invalid_correction", "The correction type does not match the rating."
            )
        if request.decision == "insufficient_evidence":
            if not prediction.allowed_operations.mark_insufficient_evidence:
                self._invalid_decision()
        elif request.decision != "corrected":
            self._invalid_decision()
        scale = next(
            item
            for item in policy.rating_scales
            if item.dimension_identifier == original.dimension_identifier
        )
        if correction.corrected_score_status == "available":
            if correction.corrected_score not in scale.allowed_scores:
                raise ResearchAnnotationServiceError(
                    "invalid_correction", "The corrected score is outside the declared scale."
                )
            if correction.corrected_assessability == "not_assessable":
                raise ResearchAnnotationServiceError(
                    "invalid_correction", "A not-assessable rating cannot have a score."
                )
        if not set(correction.corrected_evidence_turns) <= transcript_turns:
            raise ResearchAnnotationServiceError(
                "invalid_correction", "Corrected evidence references an unknown transcript turn."
            )
        score_changed = (
            correction.corrected_score != original.score
            or correction.corrected_score_status != original.score_status
        )
        evidence_changed = correction.corrected_evidence_turns != original.evidence_turns
        assessability_changed = correction.corrected_assessability != original.assessability
        if score_changed and not (
            prediction.allowed_operations.change_rating
            or prediction.allowed_operations.mark_insufficient_evidence
        ):
            self._invalid_decision()
        if evidence_changed and not prediction.allowed_operations.change_evidence:
            self._invalid_decision()
        if assessability_changed and not scale.allow_assessability_correction:
            raise ResearchAnnotationServiceError(
                "invalid_correction",
                "The policy does not allow assessability correction.",
            )
        if not score_changed and not evidence_changed and not assessability_changed:
            raise ResearchAnnotationServiceError(
                "invalid_correction", "A correction must change an allowed value."
            )

    @staticmethod
    def _validate_resolved_relations(
        inventory: tuple[ReviewablePrediction, ...],
        decisions: dict[str, ResearchReviewDecisionRevision],
    ) -> None:
        for item in inventory:
            relation = item.original_prediction
            if not isinstance(relation, ProjectedRelation):
                continue
            decision = decisions[item.prediction_id]
            if decision.decision == "rejected":
                continue
            endpoint_decisions = (
                decisions[relation.source_annotation_id],
                decisions[relation.target_annotation_id],
            )
            if any(endpoint.decision == "rejected" for endpoint in endpoint_decisions):
                raise ResearchAnnotationServiceError(
                    "completion_blocked",
                    "A confirmed relation cannot retain a rejected endpoint.",
                )

    def _record(self, entity: ResearchAnnotationSet) -> AnnotationSetRecord:
        run = self.run_service.get_run(entity.evaluation_run_id)
        policy = policy_for_envelope(run.envelope)
        inventory = self._inventory(entity)
        decision_entities = self.repository.list_decision_revisions(entity.id)
        decisions = tuple(self._decision_record(item) for item in decision_entities)
        effective_map: dict[str, DecisionRevisionRecord] = {}
        for decision in decisions:
            effective_map[decision.prediction_id] = decision
        effective = tuple(
            effective_map[item.prediction_id]
            for item in inventory
            if item.prediction_id in effective_map
        )
        progress = self._progress(inventory, effective)
        transitions = tuple(
            AnnotationTransitionRecord(
                transition_uuid=item.id,
                from_status=item.from_status,
                to_status=item.to_status,
                set_revision=item.set_revision,
                reason=item.reason,
                actor_reference=pseudonymous_reviewer_reference(item.actor_user_id),
                created_at=item.created_at,
            )
            for item in self.repository.list_transitions(entity.id)
        )
        return AnnotationSetRecord(
            annotation_set_uuid=entity.id,
            evaluation_run_uuid=entity.evaluation_run_id,
            transcript_hash=entity.transcript_hash,
            transcript_matches_current=run.transcript_matches_current,
            framework_identifier=entity.framework_identifier,
            framework_version=entity.framework_version,
            annotation_policy=policy,
            guideline_identifier=entity.guideline_identifier,
            guideline_version=entity.guideline_version,
            reviewer_reference=pseudonymous_reviewer_reference(entity.reviewer_user_id),
            status=entity.status,
            locked=entity.status == "complete",
            revision=entity.revision,
            eligible_predictions=inventory,
            decision_revisions=decisions,
            effective_decisions=effective,
            transitions=transitions,
            progress=progress,
            resolved_projection=ResearchProjection(),
            set_note=entity.set_note,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            completed_at=entity.completed_at,
            locked_at=entity.locked_at,
            reopened_at=entity.reopened_at,
        )

    @staticmethod
    def _progress(
        inventory: tuple[ReviewablePrediction, ...],
        effective: tuple[DecisionRevisionRecord, ...],
    ) -> ReviewProgress:
        counts = {
            "confirmed": 0,
            "corrected": 0,
            "rejected": 0,
            "insufficient_evidence": 0,
        }
        for decision in effective:
            counts[decision.decision] += 1
        return ReviewProgress(
            total=len(inventory),
            confirmed=counts["confirmed"],
            corrected=counts["corrected"],
            rejected=counts["rejected"],
            insufficient_evidence=counts["insufficient_evidence"],
            unreviewed=len(inventory) - len(effective),
        )

    @staticmethod
    def _inventory(entity: ResearchAnnotationSet) -> tuple[ReviewablePrediction, ...]:
        return _INVENTORY_ADAPTER.validate_json(entity.eligible_predictions_json)

    @staticmethod
    def _decision_record(entity: ResearchReviewDecisionRevision) -> DecisionRevisionRecord:
        correction = (
            _CORRECTION_ADAPTER.validate_json(entity.correction_json)
            if entity.correction_json is not None
            else None
        )
        return DecisionRevisionRecord(
            decision_uuid=entity.id,
            prediction_id=entity.prediction_id,
            projection_type=entity.projection_type,
            revision_number=entity.revision_number,
            decision=entity.decision,
            correction=correction,
            reviewer_note=entity.reviewer_note,
            reviewer_reference=pseudonymous_reviewer_reference(entity.reviewer_user_id),
            supersedes_uuid=entity.supersedes_id,
            created_at=entity.created_at,
        )

    def _effective_decision_entities(
        self,
        annotation_set_id: UUID,
    ) -> dict[str, ResearchReviewDecisionRevision]:
        effective: dict[str, ResearchReviewDecisionRevision] = {}
        for decision in self.repository.list_decision_revisions(annotation_set_id):
            effective[decision.prediction_id] = decision
        return effective
