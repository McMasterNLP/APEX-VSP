"""Strict Item 2A contracts for saved runs and append-only human review."""

from __future__ import annotations

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.time import UTCDateTime
from domain.models.research_evaluation import (
    AnnotationOperationCapabilities,
    DimensionRating,
    ProjectedRelation,
    ProjectionAnnotationCapabilities,
    ResearchEvaluationEnvelope,
    ResearchFinding,
    ResearchProjection,
    ResearchTranscriptTurn,
    SourceReference,
    SpanAnnotation,
    TurnLabel,
)

ANNOTATION_SCHEMA_VERSION = "1.1"
MAX_REVIEWER_NOTE_LENGTH = 1_000
MAX_SET_NOTE_LENGTH = 1_000
MAX_REOPEN_REASON_LENGTH = 500
REVIEWED_PROJECTION_LIMITATION = (
    "Item 2A creates a human-reviewed prediction set, not a complete gold-standard "
    "dataset; human-added false negatives are unsupported."
)
REFERENCE_PROJECTION_LIMITATION = (
    "Item 2B extends the human-reviewed prediction set into a versioned reference "
    "projection whose supported validation uses depend on audited coverage; it is "
    "not a complete gold-standard or an adjudicated gold standard."
)

ReviewProjectionType = Literal[
    "span_annotation", "turn_label", "relation", "dimension_rating", "finding"
]
AnnotationSetStatus = Literal["draft", "in_review", "complete"]
ReviewDecision = Literal[
    "confirmed", "rejected", "corrected", "insufficient_evidence"
]
CoverageLevel = Literal[
    "not_assessed",
    "prediction_review_only",
    "exhaustive",
    "fixed_inventory_complete",
]
HumanAnnotationOperation = Literal[
    "create",
    "relabel",
    "edit_attributes",
    "adjust_span",
    "retire",
    "restore",
]
AuthoredRelationOperation = Literal["create", "correct", "retire", "restore"]
AuthoredObjectStatus = Literal["active", "retired"]


class StrictAnnotationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


ReviewableProjection = Annotated[
    SpanAnnotation | TurnLabel | ProjectedRelation | DimensionRating | ResearchFinding,
    Field(discriminator="projection_type"),
]


class LabelPolicy(StrictAnnotationModel):
    projection_type: Literal["span_annotation", "turn_label"]
    allowed_labels: tuple[str, ...] = Field(min_length=1)
    allowed_dimensions: tuple[str, ...] = ()
    allow_null_dimension: bool = True


class RatingScalePolicy(StrictAnnotationModel):
    dimension_identifier: str = Field(min_length=1, max_length=100)
    allowed_scores: tuple[float, ...] = Field(min_length=1)
    allowed_assessability: tuple[
        Literal["text_assessable", "partially_assessable", "not_assessable"], ...
    ] = (
        "text_assessable",
        "partially_assessable",
        "not_assessable",
    )
    allow_assessability_correction: bool = False

    @model_validator(mode="after")
    def validate_scores(self) -> Self:
        if tuple(sorted(set(self.allowed_scores))) != self.allowed_scores:
            raise ValueError("Allowed rating scores must be unique and sorted.")
        return self


class SpanAttributeValue(StrictAnnotationModel):
    identifier: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,99}$")
    value: str = Field(min_length=1, max_length=100)


class SpanAttributePolicy(StrictAnnotationModel):
    identifier: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,99}$")
    display_name: str = Field(min_length=1, max_length=100)
    allowed_values: tuple[str, ...] = Field(min_length=1)
    allowed_for_labels: tuple[str, ...] = Field(min_length=1)
    required_for_labels: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_attribute_policy(self) -> Self:
        if len(set(self.allowed_values)) != len(self.allowed_values):
            raise ValueError("Attribute values must be unique.")
        if not set(self.required_for_labels) <= set(self.allowed_for_labels):
            raise ValueError("Required attribute labels must also allow the attribute.")
        return self


class SpanAuthoringPolicy(StrictAnnotationModel):
    supported: bool = False
    offset_convention: Literal["unicode_code_point_half_open"] = (
        "unicode_code_point_half_open"
    )
    overlap_policy: Literal["allow", "forbid"] = "allow"
    contiguous_only: Literal[True] = True
    single_turn_only: Literal[True] = True
    exhaustive_annotation_meaningful: bool = False
    guideline_help_text: str = Field(default="", max_length=1_000)
    attribute_policies: tuple[SpanAttributePolicy, ...] = ()


class RelationTypePolicy(StrictAnnotationModel):
    relation_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,99}$")
    allowed_source_labels: tuple[str, ...] = Field(min_length=1)
    allowed_target_labels: tuple[str, ...] = Field(min_length=1)
    allow_self_relation: bool = False


class CoveragePolicy(StrictAnnotationModel):
    supported_values: tuple[CoverageLevel, ...] = (
        "not_assessed",
        "prediction_review_only",
        "fixed_inventory_complete",
    )
    exhaustive_span_annotations: bool = False
    exhaustive_relations: bool = False

    @model_validator(mode="after")
    def validate_coverage_values(self) -> Self:
        if not self.supported_values or self.supported_values[0] != "not_assessed":
            raise ValueError("Coverage policy must begin with not_assessed.")
        if len(set(self.supported_values)) != len(self.supported_values):
            raise ValueError("Coverage policy values must be unique.")
        if (
            self.exhaustive_span_annotations or self.exhaustive_relations
        ) and "exhaustive" not in self.supported_values:
            raise ValueError("Exhaustive tasks require exhaustive coverage support.")
        return self


class AnnotationPolicyDescriptor(StrictAnnotationModel):
    policy_identifier: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,99}$")
    policy_version: str = Field(min_length=1, max_length=50)
    guideline_identifier: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,99}$")
    guideline_version: str = Field(min_length=1, max_length=50)
    guideline_validation_status: Literal[
        "engineering_unvalidated", "experimental_unvalidated", "approved"
    ]
    framework_identifier: str = Field(min_length=1, max_length=100)
    supported_envelope_schema_versions: tuple[str, ...] = ("1.0",)
    supported_adapter_versions: tuple[str, ...] = Field(min_length=1)
    operations: ProjectionAnnotationCapabilities
    label_policies: tuple[LabelPolicy, ...] = ()
    rating_scales: tuple[RatingScalePolicy, ...] = ()
    span_authoring: SpanAuthoringPolicy = Field(default_factory=SpanAuthoringPolicy)
    relation_types: tuple[RelationTypePolicy, ...] = ()
    coverage: CoveragePolicy = Field(default_factory=CoveragePolicy)

    @model_validator(mode="after")
    def validate_authoring_capabilities(self) -> Self:
        span_operations = self.operations.span_annotation
        relation_operations = self.operations.relation
        if self.span_authoring.supported != span_operations.add_annotation:
            raise ValueError("Span policy and add-annotation capability must agree.")
        if span_operations.adjust_span and not self.span_authoring.supported:
            raise ValueError("Span adjustment requires span-authoring support.")
        if relation_operations.add_relation != bool(self.relation_types):
            raise ValueError("Relation policy and add-relation capability must agree.")
        return self


class ReviewablePrediction(StrictAnnotationModel):
    prediction_id: str = Field(min_length=1, max_length=100)
    projection_type: ReviewProjectionType
    original_prediction: ReviewableProjection
    allowed_operations: AnnotationOperationCapabilities

    @model_validator(mode="after")
    def validate_projection(self) -> Self:
        if self.original_prediction.projection_type != self.projection_type:
            raise ValueError("Prediction inventory projection types must agree.")
        expected_id = prediction_identifier(self.original_prediction)
        if expected_id != self.prediction_id:
            raise ValueError("Prediction inventory identifier does not match its snapshot.")
        if not (self.allowed_operations.confirm or self.allowed_operations.reject):
            raise ValueError("Reviewable predictions require confirm or reject capability.")
        return self


class SpanCorrection(StrictAnnotationModel):
    correction_type: Literal["span_annotation"] = "span_annotation"
    corrected_label: str = Field(min_length=1, max_length=100)
    corrected_dimension: str | None = Field(default=None, max_length=100)
    corrected_start_char: int | None = Field(default=None, strict=True, ge=0)
    corrected_end_char: int | None = Field(default=None, strict=True, ge=0)
    corrected_text: str | None = Field(default=None, max_length=10_000)
    transcript_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    corrected_turn_number: int | None = Field(default=None, strict=True, ge=1)
    corrected_speaker: Literal["clinician", "patient"] | None = None
    corrected_attributes: tuple[SpanAttributeValue, ...] = ()

    @model_validator(mode="after")
    def validate_boundary_shape(self) -> Self:
        boundary_values = (
            self.corrected_start_char,
            self.corrected_end_char,
            self.corrected_text,
            self.transcript_hash,
            self.corrected_turn_number,
            self.corrected_speaker,
        )
        supplied = [value is not None for value in boundary_values]
        if any(supplied) and not all(supplied):
            raise ValueError("A boundary correction requires complete selection integrity data.")
        if (
            self.corrected_start_char is not None
            and self.corrected_end_char <= self.corrected_start_char
        ):
            raise ValueError("Corrected span end must be greater than start.")
        _validate_attribute_values(self.corrected_attributes)
        return self


class TurnLabelCorrection(StrictAnnotationModel):
    correction_type: Literal["turn_label"] = "turn_label"
    corrected_label: str = Field(min_length=1, max_length=100)
    corrected_dimension: str | None = Field(default=None, max_length=100)


class DimensionRatingCorrection(StrictAnnotationModel):
    correction_type: Literal["dimension_rating"] = "dimension_rating"
    corrected_score: float | None = Field(default=None, allow_inf_nan=False)
    corrected_score_status: Literal[
        "available", "insufficient_evidence", "not_assessable"
    ]
    corrected_assessability: Literal[
        "text_assessable", "partially_assessable", "not_assessable"
    ]
    corrected_evidence_turns: tuple[int, ...] = ()

    @model_validator(mode="after")
    def validate_rating_state(self) -> Self:
        if self.corrected_score_status == "available":
            if self.corrected_score is None:
                raise ValueError("An available corrected rating requires a score.")
        elif self.corrected_score is not None:
            raise ValueError("An unavailable corrected rating requires a null score.")
        if tuple(sorted(set(self.corrected_evidence_turns))) != self.corrected_evidence_turns:
            raise ValueError("Corrected evidence turns must be unique and sorted.")
        if any(turn < 1 for turn in self.corrected_evidence_turns):
            raise ValueError("Corrected evidence turns must be positive.")
        return self


TypedCorrection = Annotated[
    SpanCorrection | TurnLabelCorrection | DimensionRatingCorrection,
    Field(discriminator="correction_type"),
]


class CanonicalSpanSelection(StrictAnnotationModel):
    transcript_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    start_turn_number: int = Field(strict=True, ge=1)
    end_turn_number: int = Field(strict=True, ge=1)
    speaker: Literal["clinician", "patient"]
    start_offset: int = Field(strict=True, ge=0)
    end_offset: int = Field(strict=True, ge=0)
    selected_text: str = Field(min_length=1, max_length=10_000)

    @model_validator(mode="after")
    def validate_selection_shape(self) -> Self:
        if self.start_turn_number != self.end_turn_number:
            raise ValueError("A span selection must stay within one transcript turn.")
        if self.end_offset <= self.start_offset:
            raise ValueError("A span selection end must be greater than start.")
        if not self.selected_text.strip():
            raise ValueError("A span selection cannot contain only whitespace.")
        return self


class HumanAnnotationCreateRequest(StrictAnnotationModel):
    expected_set_revision: int = Field(strict=True, ge=0)
    selection: CanonicalSpanSelection
    label: str = Field(min_length=1, max_length=100)
    dimension: str | None = Field(default=None, max_length=100)
    attributes: tuple[SpanAttributeValue, ...] = ()
    reviewer_note: str | None = Field(default=None, max_length=MAX_REVIEWER_NOTE_LENGTH)

    @model_validator(mode="after")
    def validate_attributes(self) -> Self:
        _validate_attribute_values(self.attributes)
        return self


class HumanAnnotationRevisionRequest(StrictAnnotationModel):
    expected_set_revision: int = Field(strict=True, ge=0)
    expected_annotation_revision: int = Field(strict=True, ge=1)
    operation: Literal[
        "relabel", "edit_attributes", "adjust_span", "retire", "restore"
    ]
    selection: CanonicalSpanSelection | None = None
    label: str | None = Field(default=None, min_length=1, max_length=100)
    dimension: str | None = Field(default=None, max_length=100)
    attributes: tuple[SpanAttributeValue, ...] | None = None
    reviewer_note: str | None = Field(default=None, max_length=MAX_REVIEWER_NOTE_LENGTH)

    @model_validator(mode="after")
    def validate_operation_payload(self) -> Self:
        if self.operation == "adjust_span" and self.selection is None:
            raise ValueError("Span adjustment requires a canonical selection.")
        if self.operation == "relabel" and self.label is None:
            raise ValueError("Relabel requires a label.")
        if self.operation == "edit_attributes" and self.attributes is None:
            raise ValueError("Attribute editing requires attributes.")
        if self.operation in {"retire", "restore"} and any(
            value is not None
            for value in (self.selection, self.label, self.dimension, self.attributes)
        ):
            raise ValueError("Retire and restore do not accept replacement span fields.")
        if self.attributes is not None:
            _validate_attribute_values(self.attributes)
        return self


class AuthoredRelationCreateRequest(StrictAnnotationModel):
    expected_set_revision: int = Field(strict=True, ge=0)
    source_annotation_id: str = Field(pattern=r"^span_[0-9a-f]{40}$")
    target_annotation_id: str = Field(pattern=r"^span_[0-9a-f]{40}$")
    relation_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,99}$")
    reviewer_note: str | None = Field(default=None, max_length=MAX_REVIEWER_NOTE_LENGTH)


class AuthoredRelationRevisionRequest(StrictAnnotationModel):
    expected_set_revision: int = Field(strict=True, ge=0)
    expected_relation_revision: int = Field(strict=True, ge=1)
    operation: Literal["correct", "retire", "restore"]
    source_annotation_id: str | None = Field(
        default=None, pattern=r"^span_[0-9a-f]{40}$"
    )
    target_annotation_id: str | None = Field(
        default=None, pattern=r"^span_[0-9a-f]{40}$"
    )
    relation_type: str | None = Field(
        default=None, pattern=r"^[a-z][a-z0-9_.-]{1,99}$"
    )
    reviewer_note: str | None = Field(default=None, max_length=MAX_REVIEWER_NOTE_LENGTH)

    @model_validator(mode="after")
    def validate_operation_payload(self) -> Self:
        replacement = (
            self.source_annotation_id,
            self.target_annotation_id,
            self.relation_type,
        )
        if self.operation == "correct" and not all(replacement):
            raise ValueError("Relation correction requires type and both endpoints.")
        if self.operation in {"retire", "restore"} and any(replacement):
            raise ValueError("Retire and restore do not accept replacement relation fields.")
        return self


class CoverageDeclarationWriteRequest(StrictAnnotationModel):
    expected_set_revision: int = Field(strict=True, ge=0)
    coverage: CoverageLevel
    reviewer_note: str | None = Field(default=None, max_length=MAX_REVIEWER_NOTE_LENGTH)


class ResearchEvaluationRunSaveRequest(StrictAnnotationModel):
    evaluator_identifier: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,99}$")
    allow_live: bool = False
    provider: Literal["openai", "gemini"] | None = None
    model_identifier: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_live_options(self) -> Self:
        if not self.allow_live and (self.provider is not None or self.model_identifier is not None):
            raise ValueError("Provider/model overrides require allow_live=true.")
        return self


class AnnotationSetCreateRequest(StrictAnnotationModel):
    guideline_identifier: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,99}$")
    guideline_version: str = Field(min_length=1, max_length=50)
    set_note: str | None = Field(default=None, max_length=MAX_SET_NOTE_LENGTH)


class ReviewDecisionWriteRequest(StrictAnnotationModel):
    expected_set_revision: int = Field(strict=True, ge=0)
    expected_decision_revision: int | None = Field(default=None, strict=True, ge=1)
    decision: ReviewDecision
    correction: TypedCorrection | None = None
    reviewer_note: str | None = Field(default=None, max_length=MAX_REVIEWER_NOTE_LENGTH)

    @model_validator(mode="after")
    def validate_decision_shape(self) -> Self:
        if self.decision in {"confirmed", "rejected"} and self.correction is not None:
            raise ValueError("Confirmed or rejected decisions cannot carry a correction.")
        if self.decision in {"corrected", "insufficient_evidence"} and self.correction is None:
            raise ValueError("Corrected decisions require a typed correction.")
        if self.decision == "insufficient_evidence":
            if not isinstance(self.correction, DimensionRatingCorrection):
                raise ValueError("Insufficient evidence is available only for ratings.")
            if self.correction.corrected_score_status != "insufficient_evidence":
                raise ValueError("Insufficient-evidence correction status must agree.")
        return self


class AnnotationSetCompleteRequest(StrictAnnotationModel):
    expected_set_revision: int = Field(strict=True, ge=0)


class AnnotationSetReopenRequest(StrictAnnotationModel):
    expected_set_revision: int = Field(strict=True, ge=0)
    reason: str = Field(min_length=1, max_length=MAX_REOPEN_REASON_LENGTH)


class AnnotationExportRequest(StrictAnnotationModel):
    profile: Literal["full_review", "resolved_projection", "audit_history"]
    include_transcript_content: bool = False


class EvaluationRunRecord(StrictAnnotationModel):
    run_uuid: UUID
    source_session_id: int
    envelope: ResearchEvaluationEnvelope
    transcript_snapshot: tuple[ResearchTranscriptTurn, ...]
    creator_reference: str
    created_at: UTCDateTime
    transcript_matches_current: bool
    current_transcript_hash: str | None = None
    annotation_policy: AnnotationPolicyDescriptor


class EvaluationRunSummary(StrictAnnotationModel):
    run_uuid: UUID
    item1_run_id: str
    evaluator_identifier: str
    evaluator_version: str
    framework_identifier: str
    framework_version: str
    transcript_hash: str
    execution_mode: Literal["offline", "live"]
    status: Literal["success", "failed", "refused"]
    created_at: UTCDateTime
    transcript_matches_current: bool


class DecisionRevisionRecord(StrictAnnotationModel):
    decision_uuid: UUID
    prediction_id: str
    projection_type: ReviewProjectionType
    revision_number: int = Field(ge=1)
    decision: ReviewDecision
    correction: TypedCorrection | None = None
    reviewer_note: str | None = None
    reviewer_reference: str
    supersedes_uuid: UUID | None = None
    created_at: UTCDateTime


class HumanAnnotationRevisionRecord(StrictAnnotationModel):
    revision_uuid: UUID
    annotation_id: str = Field(pattern=r"^span_[0-9a-f]{40}$")
    revision_number: int = Field(ge=1)
    set_revision: int = Field(ge=1)
    operation: HumanAnnotationOperation
    status: AuthoredObjectStatus
    origin: Literal["human_added"] = "human_added"
    transcript_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    turn_number: int = Field(ge=1)
    speaker: Literal["clinician", "patient"]
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=1)
    selected_text: str
    label: str
    dimension: str | None = None
    attributes: tuple[SpanAttributeValue, ...] = ()
    reviewer_note: str | None = None
    reviewer_reference: str
    policy_identifier: str
    policy_version: str
    guideline_identifier: str
    guideline_version: str
    supersedes_uuid: UUID | None = None
    created_at: UTCDateTime


class AuthoredRelationRevisionRecord(StrictAnnotationModel):
    revision_uuid: UUID
    relation_id: str = Field(pattern=r"^relation_[0-9a-f]{40}$")
    revision_number: int = Field(ge=1)
    set_revision: int = Field(ge=1)
    operation: AuthoredRelationOperation
    status: AuthoredObjectStatus
    origin: Literal["human_added"] = "human_added"
    transcript_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_annotation_id: str = Field(pattern=r"^span_[0-9a-f]{40}$")
    target_annotation_id: str = Field(pattern=r"^span_[0-9a-f]{40}$")
    relation_type: str
    reviewer_note: str | None = None
    reviewer_reference: str
    policy_identifier: str
    policy_version: str
    guideline_identifier: str
    guideline_version: str
    supersedes_uuid: UUID | None = None
    created_at: UTCDateTime


class CoverageDeclarationRecord(StrictAnnotationModel):
    revision_uuid: UUID
    coverage_revision: int = Field(ge=1)
    set_revision: int = Field(ge=1)
    coverage: CoverageLevel
    reviewer_note: str | None = None
    reviewer_reference: str
    policy_identifier: str
    policy_version: str
    guideline_identifier: str
    guideline_version: str
    supersedes_uuid: UUID | None = None
    created_at: UTCDateTime


class MetricEligibilityRecord(StrictAnnotationModel):
    metric_identifier: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,99}$")
    eligible: bool
    reason_code: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,99}$")
    explanation: str = Field(min_length=1, max_length=500)
    required_coverage: CoverageLevel
    current_coverage: CoverageLevel


class ValidationEligibilityRecord(StrictAnnotationModel):
    eligible_metric_identifiers: tuple[str, ...]
    ineligible_metric_identifiers: tuple[str, ...]
    metrics: tuple[MetricEligibilityRecord, ...]


class ResearchReferenceProjection(StrictAnnotationModel):
    schema_version: Literal["1.0"] = "1.0"
    annotation_contract_version: Literal["1.1"] = ANNOTATION_SCHEMA_VERSION
    annotation_set_uuid: UUID
    evaluation_run_uuid: UUID
    item1_run_id: str
    transcript_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    transcript_projection_version: str
    framework_identifier: str
    framework_version: str
    policy_identifier: str
    policy_version: str
    guideline_identifier: str
    guideline_version: str
    coverage: CoverageLevel
    projection: ResearchProjection
    limitation: str = REFERENCE_PROJECTION_LIMITATION


class AnnotationTransitionRecord(StrictAnnotationModel):
    transition_uuid: UUID
    from_status: AnnotationSetStatus
    to_status: AnnotationSetStatus
    set_revision: int = Field(ge=1)
    reason: str | None = None
    actor_reference: str
    created_at: UTCDateTime


class ReviewProgress(StrictAnnotationModel):
    total: int = Field(ge=0)
    confirmed: int = Field(ge=0)
    corrected: int = Field(ge=0)
    rejected: int = Field(ge=0)
    insufficient_evidence: int = Field(ge=0)
    unreviewed: int = Field(ge=0)


class AnnotationSetRecord(StrictAnnotationModel):
    schema_version: Literal["1.1"] = ANNOTATION_SCHEMA_VERSION
    annotation_set_uuid: UUID
    evaluation_run_uuid: UUID
    transcript_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    transcript_matches_current: bool
    framework_identifier: str
    framework_version: str
    annotation_policy: AnnotationPolicyDescriptor
    guideline_identifier: str
    guideline_version: str
    reviewer_reference: str
    status: AnnotationSetStatus
    locked: bool
    revision: int = Field(ge=0)
    eligible_predictions: tuple[ReviewablePrediction, ...]
    decision_revisions: tuple[DecisionRevisionRecord, ...]
    effective_decisions: tuple[DecisionRevisionRecord, ...]
    transitions: tuple[AnnotationTransitionRecord, ...]
    progress: ReviewProgress
    resolved_projection: ResearchProjection
    human_annotation_revisions: tuple[HumanAnnotationRevisionRecord, ...] = ()
    active_human_annotations: tuple[HumanAnnotationRevisionRecord, ...] = ()
    authored_relation_revisions: tuple[AuthoredRelationRevisionRecord, ...] = ()
    active_authored_relations: tuple[AuthoredRelationRevisionRecord, ...] = ()
    coverage_revisions: tuple[CoverageDeclarationRecord, ...] = ()
    coverage: CoverageDeclarationRecord | None = None
    coverage_level: CoverageLevel = "not_assessed"
    reference_projection: ResearchReferenceProjection | None = None
    validation_eligibility: ValidationEligibilityRecord | None = None
    set_note: str | None = None
    created_at: UTCDateTime
    updated_at: UTCDateTime
    completed_at: UTCDateTime | None = None
    locked_at: UTCDateTime | None = None
    reopened_at: UTCDateTime | None = None


class AnnotationWorkspaceRecord(StrictAnnotationModel):
    run: EvaluationRunRecord
    annotation_set: AnnotationSetRecord


def prediction_identifier(prediction: ReviewableProjection) -> str:
    """Return the stable Item 1 identifier for any reviewable projection."""

    if isinstance(prediction, ProjectedRelation):
        return prediction.relation_id
    if isinstance(prediction, DimensionRating):
        return prediction.rating_id
    if isinstance(prediction, ResearchFinding):
        return prediction.finding_id
    return prediction.prediction_id


def prediction_source_reference(prediction: ReviewableProjection) -> SourceReference:
    return prediction.source_reference


def _validate_attribute_values(values: tuple[SpanAttributeValue, ...]) -> None:
    identifiers = tuple(item.identifier for item in values)
    if identifiers != tuple(sorted(identifiers)) or len(set(identifiers)) != len(
        identifiers
    ):
        raise ValueError("Span attributes must be unique and sorted by identifier.")
