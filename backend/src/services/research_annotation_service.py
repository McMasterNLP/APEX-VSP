"""Reviewer-specific annotation lifecycle and append-only decision service."""

from __future__ import annotations

import json
import hashlib
from typing import Literal
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.time import utc_now
from domain.entities.research_annotation import (
    ResearchAuthoredRelationRevision,
    ResearchAnnotationSet,
    ResearchAnnotationTransition,
    ResearchCoverageDeclarationRevision,
    ResearchHumanAnnotationRevision,
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
    AuthoredRelationCreateRequest,
    AuthoredRelationRevisionRecord,
    AuthoredRelationRevisionRequest,
    CanonicalSpanSelection,
    CoverageDeclarationRecord,
    CoverageDeclarationWriteRequest,
    DecisionRevisionRecord,
    DimensionRatingCorrection,
    HumanAnnotationCreateRequest,
    HumanAnnotationRevisionRecord,
    HumanAnnotationRevisionRequest,
    MetricEligibilityRecord,
    ResearchReferenceProjection,
    LabelPolicy,
    ReviewDecisionWriteRequest,
    ReviewProgress,
    ReviewablePrediction,
    SpanAttributeValue,
    SpanCorrection,
    TurnLabelCorrection,
    TypedCorrection,
    ValidationEligibilityRecord,
)
from domain.models.research_evaluation import (
    DimensionRating,
    ProjectedRelation,
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
from services.research_annotation_resolution import resolve_annotation_projection
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
            "invalid_selection",
            "invalid_annotation",
            "invalid_relation",
            "invalid_coverage",
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
            run.transcript_snapshot,
            annotation_set.transcript_hash,
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

    def create_human_annotation(
        self,
        annotation_set_uuid: UUID,
        request: HumanAnnotationCreateRequest,
        reviewer: User,
    ) -> AnnotationSetRecord:
        annotation_set = self._editable_set(annotation_set_uuid, reviewer)
        self._check_set_revision(annotation_set, request.expected_set_revision)
        run = self.run_service.get_run(annotation_set.evaluation_run_id)
        policy = policy_for_envelope(run.envelope)
        if not policy.span_authoring.supported:
            raise ResearchAnnotationServiceError(
                "invalid_annotation", "This evaluator does not support span authoring."
            )
        self._validate_selection(request.selection, annotation_set.transcript_hash, run.transcript_snapshot)
        self._validate_authored_label(policy, request.label, request.dimension, request.attributes)
        now = utc_now()
        annotation_set.revision += 1
        annotation_set.updated_at = now
        if annotation_set.status == "draft":
            annotation_set.status = "in_review"
        stable_id = "span_" + hashlib.sha256(
            f"{annotation_set.id}:{uuid4()}".encode()
        ).hexdigest()[:40]
        selection = request.selection
        revision = ResearchHumanAnnotationRevision(
            annotation_set_id=annotation_set.id,
            annotation_id=stable_id,
            revision_number=1,
            set_revision=annotation_set.revision,
            operation="create",
            status="active",
            transcript_hash=selection.transcript_hash,
            turn_number=selection.start_turn_number,
            speaker=selection.speaker,
            start_offset=selection.start_offset,
            end_offset=selection.end_offset,
            selected_text=selection.selected_text,
            label=request.label,
            dimension=request.dimension,
            attributes_json=json.dumps([item.model_dump(mode="json") for item in request.attributes], separators=(",", ":")),
            reviewer_note=request.reviewer_note,
            reviewer_user_id=reviewer.id,
            policy_identifier=policy.policy_identifier,
            policy_version=policy.policy_version,
            guideline_identifier=policy.guideline_identifier,
            guideline_version=policy.guideline_version,
            created_at=now,
        )
        self._persist_authoring(annotation_set, revision, self.repository.add_human_annotation_revision)
        return self.get_annotation_set(annotation_set_uuid)

    def revise_human_annotation(
        self,
        annotation_set_uuid: UUID,
        annotation_id: str,
        request: HumanAnnotationRevisionRequest,
        reviewer: User,
    ) -> AnnotationSetRecord:
        annotation_set = self._editable_set(annotation_set_uuid, reviewer)
        current_items = self.repository.list_human_annotation_revisions(annotation_set.id, annotation_id=annotation_id)
        if not current_items:
            raise ResearchAnnotationServiceError("invalid_annotation", "The human annotation was not found.")
        current = current_items[-1]
        if request.expected_set_revision != annotation_set.revision or request.expected_annotation_revision != current.revision_number:
            raise ResearchAnnotationServiceError("revision_conflict", "Newer annotation data exists; refresh before saving again.", current_set_revision=annotation_set.revision)
        if request.operation == "retire" and current.status == "retired":
            raise ResearchAnnotationServiceError("invalid_annotation", "The annotation is already retired.")
        if request.operation == "restore" and current.status == "active":
            raise ResearchAnnotationServiceError("invalid_annotation", "The annotation is already active.")
        run = self.run_service.get_run(annotation_set.evaluation_run_id)
        policy = policy_for_envelope(run.envelope)
        selection = request.selection
        if selection is not None:
            self._validate_selection(selection, annotation_set.transcript_hash, run.transcript_snapshot)
        label = request.label if request.operation == "relabel" else current.label
        dimension = request.dimension if request.operation == "relabel" else current.dimension
        attributes = request.attributes if request.operation == "edit_attributes" else tuple(
            SpanAttributeValue.model_validate(item)
            for item in json.loads(current.attributes_json)
        )
        self._validate_authored_label(policy, label, dimension, attributes)
        now = utc_now()
        annotation_set.revision += 1
        annotation_set.updated_at = now
        revision = ResearchHumanAnnotationRevision(
            annotation_set_id=annotation_set.id,
            annotation_id=annotation_id,
            revision_number=current.revision_number + 1,
            set_revision=annotation_set.revision,
            operation=request.operation,
            status="retired" if request.operation == "retire" else "active",
            transcript_hash=selection.transcript_hash if selection else current.transcript_hash,
            turn_number=selection.start_turn_number if selection else current.turn_number,
            speaker=selection.speaker if selection else current.speaker,
            start_offset=selection.start_offset if selection else current.start_offset,
            end_offset=selection.end_offset if selection else current.end_offset,
            selected_text=selection.selected_text if selection else current.selected_text,
            label=label,
            dimension=dimension,
            attributes_json=json.dumps([item.model_dump(mode="json") for item in attributes], separators=(",", ":")),
            reviewer_note=request.reviewer_note,
            reviewer_user_id=reviewer.id,
            policy_identifier=policy.policy_identifier,
            policy_version=policy.policy_version,
            guideline_identifier=policy.guideline_identifier,
            guideline_version=policy.guideline_version,
            supersedes_id=current.id,
            created_at=now,
        )
        self._persist_authoring(annotation_set, revision, self.repository.add_human_annotation_revision)
        return self.get_annotation_set(annotation_set_uuid)

    def create_authored_relation(self, annotation_set_uuid: UUID, request: AuthoredRelationCreateRequest, reviewer: User) -> AnnotationSetRecord:
        annotation_set = self._editable_set(annotation_set_uuid, reviewer)
        self._check_set_revision(annotation_set, request.expected_set_revision)
        run = self.run_service.get_run(annotation_set.evaluation_run_id)
        policy = policy_for_envelope(run.envelope)
        self._validate_relation(annotation_set, policy, request.source_annotation_id, request.target_annotation_id, request.relation_type)
        now = utc_now()
        annotation_set.revision += 1
        annotation_set.updated_at = now
        relation_id = "relation_" + hashlib.sha256(f"{annotation_set.id}:{uuid4()}".encode()).hexdigest()[:40]
        revision = ResearchAuthoredRelationRevision(
            annotation_set_id=annotation_set.id, relation_id=relation_id, revision_number=1,
            set_revision=annotation_set.revision, operation="create", status="active",
            transcript_hash=annotation_set.transcript_hash,
            source_annotation_id=request.source_annotation_id, target_annotation_id=request.target_annotation_id,
            relation_type=request.relation_type, reviewer_note=request.reviewer_note,
            reviewer_user_id=reviewer.id, policy_identifier=policy.policy_identifier,
            policy_version=policy.policy_version, guideline_identifier=policy.guideline_identifier,
            guideline_version=policy.guideline_version, created_at=now,
        )
        self._persist_authoring(annotation_set, revision, self.repository.add_authored_relation_revision)
        return self.get_annotation_set(annotation_set_uuid)

    def revise_authored_relation(self, annotation_set_uuid: UUID, relation_id: str, request: AuthoredRelationRevisionRequest, reviewer: User) -> AnnotationSetRecord:
        annotation_set = self._editable_set(annotation_set_uuid, reviewer)
        items = self.repository.list_authored_relation_revisions(annotation_set.id, relation_id=relation_id)
        if not items:
            raise ResearchAnnotationServiceError("invalid_relation", "The authored relation was not found.")
        current = items[-1]
        if request.expected_set_revision != annotation_set.revision or request.expected_relation_revision != current.revision_number:
            raise ResearchAnnotationServiceError("revision_conflict", "Newer relation data exists; refresh before saving again.", current_set_revision=annotation_set.revision)
        source = request.source_annotation_id if request.operation == "correct" else current.source_annotation_id
        target = request.target_annotation_id if request.operation == "correct" else current.target_annotation_id
        relation_type = request.relation_type if request.operation == "correct" else current.relation_type
        if request.operation in {"correct", "restore"}:
            self._validate_relation(annotation_set, policy_for_envelope(self.run_service.get_run(annotation_set.evaluation_run_id).envelope), source, target, relation_type, exclude_relation_id=relation_id)
        now = utc_now()
        annotation_set.revision += 1
        annotation_set.updated_at = now
        revision = ResearchAuthoredRelationRevision(
            annotation_set_id=annotation_set.id, relation_id=relation_id,
            revision_number=current.revision_number + 1, set_revision=annotation_set.revision,
            operation=request.operation, status="retired" if request.operation == "retire" else "active",
            transcript_hash=current.transcript_hash, source_annotation_id=source,
            target_annotation_id=target, relation_type=relation_type,
            reviewer_note=request.reviewer_note, reviewer_user_id=reviewer.id,
            policy_identifier=current.policy_identifier, policy_version=current.policy_version,
            guideline_identifier=current.guideline_identifier, guideline_version=current.guideline_version,
            supersedes_id=current.id, created_at=now,
        )
        self._persist_authoring(annotation_set, revision, self.repository.add_authored_relation_revision)
        return self.get_annotation_set(annotation_set_uuid)

    def declare_coverage(self, annotation_set_uuid: UUID, request: CoverageDeclarationWriteRequest, reviewer: User) -> AnnotationSetRecord:
        annotation_set = self._editable_set(annotation_set_uuid, reviewer)
        self._check_set_revision(annotation_set, request.expected_set_revision)
        policy = policy_for_envelope(self.run_service.get_run(annotation_set.evaluation_run_id).envelope)
        if request.coverage not in policy.coverage.supported_values:
            raise ResearchAnnotationServiceError("invalid_coverage", "This coverage value is not supported by the annotation policy.")
        if request.coverage == "exhaustive":
            missing = len(self._inventory(annotation_set)) - len(self._effective_decision_entities(annotation_set.id))
            if missing:
                raise ResearchAnnotationServiceError("invalid_coverage", "Exhaustive coverage requires every presented prediction to be reviewed.")
        previous = self.repository.list_coverage_revisions(annotation_set.id)
        now = utc_now()
        annotation_set.revision += 1
        annotation_set.updated_at = now
        revision = ResearchCoverageDeclarationRevision(
            annotation_set_id=annotation_set.id, coverage_revision=len(previous) + 1,
            set_revision=annotation_set.revision, coverage=request.coverage,
            reviewer_note=request.reviewer_note, reviewer_user_id=reviewer.id,
            policy_identifier=policy.policy_identifier, policy_version=policy.policy_version,
            guideline_identifier=policy.guideline_identifier, guideline_version=policy.guideline_version,
            supersedes_id=previous[-1].id if previous else None, created_at=now,
        )
        self._persist_authoring(annotation_set, revision, self.repository.add_coverage_revision)
        return self.get_annotation_set(annotation_set_uuid)

    def _editable_set(self, annotation_set_uuid: UUID, reviewer: User) -> ResearchAnnotationSet:
        annotation_set = self._locked_set(annotation_set_uuid)
        self._require_reviewer(annotation_set, reviewer)
        if annotation_set.status == "complete":
            raise ResearchAnnotationServiceError("annotation_set_locked", "Complete annotation sets are locked.")
        return annotation_set

    def _persist_authoring(self, annotation_set, revision, add_revision) -> None:
        try:
            add_revision(revision)
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            current = self.repository.get_annotation_set(annotation_set.id)
            raise ResearchAnnotationServiceError(
                "revision_conflict", "Newer annotation data exists; refresh before saving again.",
                current_set_revision=current.revision if current else None,
            ) from error
        except ResearchAnnotationServiceError:
            self.db.rollback()
            raise
        except Exception as error:
            self.db.rollback()
            raise ResearchAnnotationServiceError("persistence_failed", "The annotation revision could not be saved.") from error

    @staticmethod
    def _validate_selection(selection: CanonicalSpanSelection, transcript_hash: str, transcript_snapshot) -> None:
        if selection.transcript_hash != transcript_hash:
            raise ResearchAnnotationServiceError("invalid_selection", "The transcript snapshot is stale; refresh before annotating.")
        turn = next((item for item in transcript_snapshot if item.turn_number == selection.start_turn_number), None)
        if turn is None:
            raise ResearchAnnotationServiceError("invalid_selection", "The selected transcript turn does not exist.")
        if turn.role != selection.speaker:
            raise ResearchAnnotationServiceError("invalid_selection", "The selected speaker does not match the immutable transcript.")
        if selection.end_offset > len(turn.text):
            raise ResearchAnnotationServiceError("invalid_selection", "The selection extends beyond the transcript turn.")
        if turn.text[selection.start_offset:selection.end_offset] != selection.selected_text:
            raise ResearchAnnotationServiceError("invalid_selection", "The selected text does not match the immutable transcript snapshot.")

    @staticmethod
    def _validate_authored_label(policy: AnnotationPolicyDescriptor, label: str, dimension: str | None, attributes) -> None:
        label_policy = next((item for item in policy.label_policies if item.projection_type == "span_annotation"), None)
        if label_policy is None or label not in label_policy.allowed_labels:
            raise ResearchAnnotationServiceError("invalid_annotation", "The selected label is not permitted by the annotation policy.")
        if dimension is not None and dimension not in label_policy.allowed_dimensions:
            raise ResearchAnnotationServiceError("invalid_annotation", "The selected dimension is not permitted by the annotation policy.")
        if label == "empathic_opportunity" and dimension is None:
            raise ResearchAnnotationServiceError("invalid_annotation", "Empathic opportunities require a dimension.")
        if label != "empathic_opportunity" and dimension is not None:
            raise ResearchAnnotationServiceError("invalid_annotation", "This label does not accept a dimension.")
        values = {item.identifier: item.value for item in attributes}
        policies = {item.identifier: item for item in policy.span_authoring.attribute_policies}
        if set(values) - set(policies):
            raise ResearchAnnotationServiceError("invalid_annotation", "An annotation attribute is not supported.")
        for identifier, value in values.items():
            attribute_policy = policies[identifier]
            if label not in attribute_policy.allowed_for_labels or value not in attribute_policy.allowed_values:
                raise ResearchAnnotationServiceError("invalid_annotation", "An annotation attribute value is not permitted.")
        if any(label in item.required_for_labels and item.identifier not in values for item in policies.values()):
            raise ResearchAnnotationServiceError("invalid_annotation", "A required annotation attribute is missing.")

    def _active_span_labels(self, annotation_set: ResearchAnnotationSet) -> dict[str, str]:
        labels: dict[str, str] = {}
        decisions = self._effective_decision_entities(annotation_set.id)
        for item in self._inventory(annotation_set):
            original = item.original_prediction
            if not isinstance(original, SpanAnnotation):
                continue
            decision = decisions.get(item.prediction_id)
            if decision is not None and decision.decision == "rejected":
                continue
            label = original.label
            if decision is not None and decision.correction_json:
                correction = _CORRECTION_ADAPTER.validate_json(decision.correction_json)
                if isinstance(correction, SpanCorrection):
                    label = correction.corrected_label
            labels[item.prediction_id] = label
        effective_human = {}
        for revision in self.repository.list_human_annotation_revisions(annotation_set.id):
            effective_human[revision.annotation_id] = revision
        labels.update({key: value.label for key, value in effective_human.items() if value.status == "active"})
        return labels

    def _validate_relation(self, annotation_set, policy, source, target, relation_type, *, exclude_relation_id=None) -> None:
        relation_policy = next((item for item in policy.relation_types if item.relation_type == relation_type), None)
        if relation_policy is None:
            raise ResearchAnnotationServiceError("invalid_relation", "The relation type is not permitted by the annotation policy.")
        labels = self._active_span_labels(annotation_set)
        if source not in labels or target not in labels:
            raise ResearchAnnotationServiceError("invalid_relation", "Both relation endpoints must be active annotations in this set.")
        if source == target and not relation_policy.allow_self_relation:
            raise ResearchAnnotationServiceError("invalid_relation", "Self-relations are not permitted.")
        if labels[source] not in relation_policy.allowed_source_labels or labels[target] not in relation_policy.allowed_target_labels:
            raise ResearchAnnotationServiceError("invalid_relation", "The relation endpoints do not satisfy the declared label constraints.")
        effective = {}
        for item in self.repository.list_authored_relation_revisions(annotation_set.id):
            effective[item.relation_id] = item
        duplicate = any(
            item.status == "active" and key != exclude_relation_id and
            (item.source_annotation_id, item.target_annotation_id, item.relation_type) == (source, target, relation_type)
            for key, item in effective.items()
        )
        if duplicate:
            raise ResearchAnnotationServiceError("invalid_relation", "An identical active relation already exists.")

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

        coverage_items = self.repository.list_coverage_revisions(annotation_set.id)
        if coverage_items and coverage_items[-1].coverage == "not_assessed":
            raise ResearchAnnotationServiceError(
                "completion_blocked", "Declare assessed coverage before completion."
            )
        active_span_ids = set(self._active_span_labels(annotation_set))
        effective_relations = {}
        for relation in self.repository.list_authored_relation_revisions(annotation_set.id):
            effective_relations[relation.relation_id] = relation
        if any(
            relation.status == "active"
            and (
                relation.source_annotation_id not in active_span_ids
                or relation.target_annotation_id not in active_span_ids
            )
            for relation in effective_relations.values()
        ):
            raise ResearchAnnotationServiceError(
                "completion_blocked", "Retire or correct relations whose endpoints are inactive."
            )

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
        if not coverage_items:
            policy = policy_for_envelope(
                self.run_service.get_run(annotation_set.evaluation_run_id).envelope
            )
            self.repository.add_coverage_revision(
                ResearchCoverageDeclarationRevision(
                    annotation_set_id=annotation_set.id,
                    coverage_revision=1,
                    set_revision=annotation_set.revision,
                    coverage="fixed_inventory_complete",
                    reviewer_note="Compatibility declaration created during completion.",
                    reviewer_user_id=reviewer.id,
                    policy_identifier=policy.policy_identifier,
                    policy_version=policy.policy_version,
                    guideline_identifier=policy.guideline_identifier,
                    guideline_version=policy.guideline_version,
                    created_at=now,
                )
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
        transcript_snapshot,
        transcript_hash: str,
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
            self._validate_label_correction(
                prediction, request, policy, transcript_snapshot, transcript_hash
            )
            return
        if isinstance(prediction.original_prediction, DimensionRating):
            self._validate_rating_correction(
                prediction,
                request,
                policy,
                {turn.turn_number for turn in transcript_snapshot},
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
        transcript_snapshot,
        transcript_hash: str,
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
        boundary_changed = isinstance(correction, SpanCorrection) and correction.corrected_start_char is not None
        if not label_changed and not dimension_changed and not boundary_changed:
            raise ResearchAnnotationServiceError(
                "invalid_correction", "A correction must change an allowed value."
            )
        if label_changed and not prediction.allowed_operations.change_label:
            self._invalid_decision()
        if dimension_changed and not prediction.allowed_operations.change_dimension:
            self._invalid_decision()
        if isinstance(original, SpanAnnotation):
            if boundary_changed:
                if not prediction.allowed_operations.adjust_span:
                    self._invalid_decision()
                if correction.corrected_turn_number != original.turn_number:
                    raise ResearchAnnotationServiceError(
                        "invalid_selection", "A model span adjustment must stay in its original turn."
                    )
                self._validate_selection(
                    CanonicalSpanSelection(
                        transcript_hash=correction.transcript_hash,
                        start_turn_number=correction.corrected_turn_number,
                        end_turn_number=correction.corrected_turn_number,
                        speaker=correction.corrected_speaker,
                        start_offset=correction.corrected_start_char,
                        end_offset=correction.corrected_end_char,
                        selected_text=correction.corrected_text,
                    ),
                    transcript_hash,
                    transcript_snapshot,
                )
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
        human_revisions = tuple(
            self._human_annotation_record(item)
            for item in self.repository.list_human_annotation_revisions(entity.id)
        )
        active_human_map = {}
        for item in human_revisions:
            active_human_map[item.annotation_id] = item
        active_human = tuple(
            item for _, item in sorted(active_human_map.items()) if item.status == "active"
        )
        relation_revisions = tuple(
            self._authored_relation_record(item)
            for item in self.repository.list_authored_relation_revisions(entity.id)
        )
        active_relation_map = {}
        for item in relation_revisions:
            active_relation_map[item.relation_id] = item
        active_relations = tuple(
            item for _, item in sorted(active_relation_map.items()) if item.status == "active"
        )
        coverage_revisions = tuple(
            self._coverage_record(item)
            for item in self.repository.list_coverage_revisions(entity.id)
        )
        coverage = coverage_revisions[-1] if coverage_revisions else None
        coverage_level = coverage.coverage if coverage else "not_assessed"
        resolved = resolve_annotation_projection(inventory, effective, active_human, active_relations)
        eligibility = self._validation_eligibility(coverage_level, effective)
        reference = ResearchReferenceProjection(
            annotation_set_uuid=entity.id,
            evaluation_run_uuid=entity.evaluation_run_id,
            item1_run_id=run.envelope.run.run_id,
            transcript_hash=entity.transcript_hash,
            transcript_projection_version=run.envelope.transcript.transcript_projection_version,
            framework_identifier=entity.framework_identifier,
            framework_version=entity.framework_version,
            policy_identifier=policy.policy_identifier,
            policy_version=policy.policy_version,
            guideline_identifier=entity.guideline_identifier,
            guideline_version=entity.guideline_version,
            coverage=coverage_level,
            projection=resolved,
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
            resolved_projection=resolved,
            human_annotation_revisions=human_revisions,
            active_human_annotations=active_human,
            authored_relation_revisions=relation_revisions,
            active_authored_relations=active_relations,
            coverage_revisions=coverage_revisions,
            coverage=coverage,
            coverage_level=coverage_level,
            reference_projection=reference,
            validation_eligibility=eligibility,
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

    @staticmethod
    def _human_annotation_record(entity: ResearchHumanAnnotationRevision) -> HumanAnnotationRevisionRecord:
        return HumanAnnotationRevisionRecord(
            revision_uuid=entity.id, annotation_id=entity.annotation_id,
            revision_number=entity.revision_number, set_revision=entity.set_revision,
            operation=entity.operation, status=entity.status,
            transcript_hash=entity.transcript_hash, turn_number=entity.turn_number,
            speaker=entity.speaker, start_offset=entity.start_offset,
            end_offset=entity.end_offset, selected_text=entity.selected_text,
            label=entity.label, dimension=entity.dimension,
            attributes=tuple(SpanAttributeValue.model_validate(item) for item in json.loads(entity.attributes_json)),
            reviewer_note=entity.reviewer_note,
            reviewer_reference=pseudonymous_reviewer_reference(entity.reviewer_user_id),
            policy_identifier=entity.policy_identifier, policy_version=entity.policy_version,
            guideline_identifier=entity.guideline_identifier, guideline_version=entity.guideline_version,
            supersedes_uuid=entity.supersedes_id, created_at=entity.created_at,
        )

    @staticmethod
    def _authored_relation_record(entity: ResearchAuthoredRelationRevision) -> AuthoredRelationRevisionRecord:
        return AuthoredRelationRevisionRecord(
            revision_uuid=entity.id, relation_id=entity.relation_id,
            revision_number=entity.revision_number, set_revision=entity.set_revision,
            operation=entity.operation, status=entity.status,
            transcript_hash=entity.transcript_hash,
            source_annotation_id=entity.source_annotation_id,
            target_annotation_id=entity.target_annotation_id,
            relation_type=entity.relation_type, reviewer_note=entity.reviewer_note,
            reviewer_reference=pseudonymous_reviewer_reference(entity.reviewer_user_id),
            policy_identifier=entity.policy_identifier, policy_version=entity.policy_version,
            guideline_identifier=entity.guideline_identifier, guideline_version=entity.guideline_version,
            supersedes_uuid=entity.supersedes_id, created_at=entity.created_at,
        )

    @staticmethod
    def _coverage_record(entity: ResearchCoverageDeclarationRevision) -> CoverageDeclarationRecord:
        return CoverageDeclarationRecord(
            revision_uuid=entity.id, coverage_revision=entity.coverage_revision,
            set_revision=entity.set_revision, coverage=entity.coverage,
            reviewer_note=entity.reviewer_note,
            reviewer_reference=pseudonymous_reviewer_reference(entity.reviewer_user_id),
            policy_identifier=entity.policy_identifier, policy_version=entity.policy_version,
            guideline_identifier=entity.guideline_identifier, guideline_version=entity.guideline_version,
            supersedes_uuid=entity.supersedes_id, created_at=entity.created_at,
        )

    @staticmethod
    def _validation_eligibility(coverage_level, effective) -> ValidationEligibilityRecord:
        reviewed = bool(effective)
        prediction_review = coverage_level in {"prediction_review_only", "fixed_inventory_complete", "exhaustive"}
        exhaustive = coverage_level == "exhaustive"
        definitions = (
            ("span_precision", prediction_review, "prediction_review_required", "prediction_review_only", "Span precision requires reviewed model predictions."),
            ("span_recall", exhaustive, "exhaustive_reference_required", "exhaustive", "Span recall requires exhaustive reference annotation."),
            ("span_f1", exhaustive, "exhaustive_reference_required", "exhaustive", "Span F1 requires exhaustive reference annotation."),
            ("label_accuracy", reviewed, "matched_instances_required", "not_assessed", "Label accuracy requires at least one reviewed instance."),
            ("relation_recall", exhaustive, "exhaustive_relations_required", "exhaustive", "Relation recall requires exhaustive relation annotation."),
            ("relation_f1", exhaustive, "exhaustive_relations_required", "exhaustive", "Relation F1 requires exhaustive relation annotation."),
            ("global_score_agreement", False, "human_score_reference_required", "not_assessed", "Global-score agreement requires a separate human score reference."),
        )
        metrics = tuple(
            MetricEligibilityRecord(
                metric_identifier=identifier, eligible=eligible,
                reason_code="eligible" if eligible else reason,
                explanation="Coverage supports this metric." if eligible else explanation,
                required_coverage=required, current_coverage=coverage_level,
            )
            for identifier, eligible, reason, required, explanation in definitions
        )
        return ValidationEligibilityRecord(
            eligible_metric_identifiers=tuple(item.metric_identifier for item in metrics if item.eligible),
            ineligible_metric_identifiers=tuple(item.metric_identifier for item in metrics if not item.eligible),
            metrics=metrics,
        )
