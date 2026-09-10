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

ANNOTATION_SCHEMA_VERSION = "1.0"
MAX_REVIEWER_NOTE_LENGTH = 1_000
MAX_SET_NOTE_LENGTH = 1_000
MAX_REOPEN_REASON_LENGTH = 500
REVIEWED_PROJECTION_LIMITATION = (
    "Item 2A creates a human-reviewed prediction set, not a complete gold-standard "
    "dataset; human-added false negatives are unsupported."
)

ReviewProjectionType = Literal[
    "span_annotation", "turn_label", "relation", "dimension_rating", "finding"
]
AnnotationSetStatus = Literal["draft", "in_review", "complete"]
ReviewDecision = Literal[
    "confirmed", "rejected", "corrected", "insufficient_evidence"
]


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
    corrected_start_char: None = None
    corrected_end_char: None = None
    corrected_text: None = None


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
    schema_version: Literal["1.0"] = ANNOTATION_SCHEMA_VERSION
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
