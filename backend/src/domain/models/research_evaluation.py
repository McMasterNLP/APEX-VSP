"""Versioned, lossless research-evaluation result contracts."""

from __future__ import annotations

import math
import re
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    field_validator,
    model_validator,
)

from domain.models.evaluator_comparison import (
    ACECTCompatibilityProjection,
    EvaluatorFrameworkResults,
)

RESEARCH_SCHEMA_VERSION = "1.0"
TRANSCRIPT_PROJECTION_VERSION = "apex-canonical-v1"
AFCE_IMPLEMENTATION_STATEMENT = (
    "AFCE-aligned, rule-based operationalization of selected constructs."
)
COMPATIBILITY_COMPARABILITY_STATEMENT = (
    "Engineering compatibility projection; not framework-equivalent."
)

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
_SAFE_SOURCE_PATH = re.compile(r"^[A-Za-z][A-Za-z0-9_.\[\]-]{0,299}$")
_PRIVATE_PATH_PARTS = {
    "database_url",
    "email",
    "session_id",
    "supabase",
    "token",
    "user_id",
}


class StrictModel(BaseModel):
    """Shared immutable, extra-forbidding model configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ApexScores(StrictModel):
    empathy_score: float = Field(ge=0, le=100, allow_inf_nan=False)
    communication_score: float = Field(ge=0, le=100, allow_inf_nan=False)
    spikes_completion_score: float = Field(ge=0, le=100, allow_inf_nan=False)
    overall_score: float = Field(ge=0, le=100, allow_inf_nan=False)


class ApexExplicitImplicitCounts(StrictModel):
    explicit: int = Field(strict=True, ge=0)
    implicit: int = Field(strict=True, ge=0)


class ApexLinkageStats(StrictModel):
    total_eos: int = Field(strict=True, ge=0)
    addressed_count: int = Field(strict=True, ge=0)
    missed_count: int = Field(strict=True, ge=0)
    addressed_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    missed_rate: float = Field(ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.addressed_count + self.missed_count != self.total_eos:
            raise ValueError("APEX linkage counts must sum to total_eos.")
        return self


class ApexNativeSpan(StrictModel):
    span_type: Literal["eo", "elicitation", "response"]
    turn_number: int = Field(strict=True, ge=1)
    start_char: int = Field(strict=True, ge=0)
    end_char: int = Field(strict=True, ge=0)
    text: str
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    provenance: Literal["rule", "ml", "llm"] | None = None
    dimension: str | None = Field(default=None, max_length=100)
    explicit_or_implicit: Literal["explicit", "implicit"] | None = None
    subtype: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_offsets(self) -> Self:
        if self.end_char <= self.start_char:
            raise ValueError("A native span end offset must be greater than its start offset.")
        if len(self.text) != self.end_char - self.start_char:
            raise ValueError("A native span text length must match its character offsets.")
        if self.span_type == "eo" and (
            self.dimension is None or self.explicit_or_implicit is None
        ):
            raise ValueError("An APEX empathy-opportunity span requires dimension and status.")
        if self.span_type in {"elicitation", "response"} and self.subtype is None:
            raise ValueError("An APEX elicitation/response span requires a subtype.")
        return self


class ApexNativeRelation(StrictModel):
    source_span_id: str = Field(min_length=1, max_length=100)
    target_span_id: str = Field(min_length=1, max_length=100)
    relation_type: Literal["responds_to", "elicits"]
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)


class ApexMissedOpportunity(StrictModel):
    span_id: str = Field(min_length=1, max_length=100)
    turn_number: int = Field(strict=True, ge=1)
    dimension: str | None = Field(default=None, max_length=100)
    explicit_or_implicit: Literal["explicit", "implicit"] | None = None
    text: str = Field(default="", max_length=500)


class ApexSpikesCoverage(StrictModel):
    covered: tuple[str, ...]
    percent: float = Field(ge=0, le=1, allow_inf_nan=False)


class ApexQuestionBreakdown(StrictModel):
    open: int = Field(strict=True, ge=0)
    closed: int = Field(strict=True, ge=0)
    eliciting: int = Field(strict=True, ge=0)
    ratio_open: float = Field(ge=0, le=1, allow_inf_nan=False)


class ApexTimelineEvent(StrictModel):
    turn_number: int = Field(strict=True, ge=1)
    type: Literal["eo", "response", "missed", "spikes"]
    label: str = Field(min_length=1, max_length=200)


class ApexSuggestedResponse(StrictModel):
    turn_number: int = Field(strict=True, ge=1)
    patient_text: str = Field(max_length=500)
    suggestion: str = Field(min_length=1, max_length=1000)


class ApexFeedbackNativeResult(StrictModel):
    """Authoritative typed research form of complete in-memory APEX feedback."""

    native_type: Literal["apex_feedback"] = "apex_feedback"
    native_version: Literal["1.0"] = "1.0"
    evaluator_family: Literal["baseline", "hybrid_v1", "hybrid_v2"]
    framework_identifier: Literal["apex-spikes-afce"] = "apex-spikes-afce"
    framework_statement: Literal[
        "AFCE-aligned, rule-based operationalization of selected constructs."
    ] = AFCE_IMPLEMENTATION_STATEMENT
    scores: ApexScores
    eo_counts_by_dimension: dict[str, ApexExplicitImplicitCounts]
    elicitation_counts_by_type: dict[str, dict[str, int]]
    response_counts_by_type: dict[str, int]
    linkage_stats: ApexLinkageStats | None = None
    missed_opportunities_by_dimension: dict[str, int] | None = None
    eo_to_elicitation_links: tuple[ApexNativeRelation, ...] = ()
    eo_to_response_links: tuple[ApexNativeRelation, ...] = ()
    missed_opportunities: tuple[ApexMissedOpportunity, ...] = ()
    eo_spans: tuple[ApexNativeSpan, ...] = ()
    elicitation_spans: tuple[ApexNativeSpan, ...] = ()
    response_spans: tuple[ApexNativeSpan, ...] = ()
    spikes_coverage: ApexSpikesCoverage
    spikes_timestamps: dict[str, JsonValue] | None = None
    spikes_strategies: dict[str, JsonValue] | None = None
    question_breakdown: ApexQuestionBreakdown
    bias_probe_info: dict[str, JsonValue] | None = None
    evaluator_metadata: dict[str, JsonValue]
    latency_ms_avg: float = Field(ge=0, allow_inf_nan=False)
    strengths: str | None = None
    areas_for_improvement: str | None = None
    detailed_feedback: str | None = None
    timeline_events: tuple[ApexTimelineEvent, ...] = ()
    suggested_responses: tuple[ApexSuggestedResponse, ...] = ()

    @model_validator(mode="after")
    def validate_span_groups(self) -> Self:
        expected = (
            (self.eo_spans, "eo"),
            (self.elicitation_spans, "elicitation"),
            (self.response_spans, "response"),
        )
        if any(span.span_type != kind for spans, kind in expected for span in spans):
            raise ValueError("APEX native spans must be stored in their matching collection.")
        return self


class ACECTNativeResearchResult(StrictModel):
    """Authoritative ACE-CT-inspired output plus its labeled compatibility bridge."""

    native_type: Literal["ace_ct_inspired"] = "ace_ct_inspired"
    native_version: Literal["1.0"] = "1.0"
    framework_results: EvaluatorFrameworkResults
    compatibility_projection: ACECTCompatibilityProjection
    experimental: Literal[True] = True
    official: Literal[False] = False
    publication_model_reproduction: Literal[False] = False


ExtensionScalar = str | int | float | bool | None


class VersionedExtensionField(StrictModel):
    """Bounded primitive field; nested arbitrary provider objects are not accepted."""

    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,99}$")
    value: ExtensionScalar | tuple[ExtensionScalar, ...]

    @field_validator("value")
    @classmethod
    def finite_and_bounded(cls, value: ExtensionScalar | tuple[ExtensionScalar, ...]):
        values = value if isinstance(value, tuple) else (value,)
        if len(values) > 100:
            raise ValueError("An extension field may contain at most 100 primitive values.")
        for item in values:
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError("Extension numeric values must be finite.")
            if isinstance(item, str) and len(item) > 2_000:
                raise ValueError("Extension string values are limited to 2,000 characters.")
        return value


class VersionedExtensionNativeResult(StrictModel):
    """Safe future native variant requiring an explicit reviewed schema identity."""

    native_type: Literal["versioned_extension"] = "versioned_extension"
    native_version: Literal["1.0"] = "1.0"
    extension_identifier: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,99}$")
    extension_schema_version: str = Field(pattern=r"^[0-9]+\.[0-9]+(?:\.[0-9]+)?$")
    provider_output_validated: Literal[True]
    fields: tuple[VersionedExtensionField, ...] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_fields(self) -> Self:
        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("Extension field names must be unique.")
        return self


FrameworkNativeResult = Annotated[
    ApexFeedbackNativeResult | ACECTNativeResearchResult | VersionedExtensionNativeResult,
    Field(discriminator="native_type"),
]
FRAMEWORK_NATIVE_RESULT_ADAPTER = TypeAdapter(FrameworkNativeResult)


class SourceReference(StrictModel):
    native_result_type: Literal[
        "apex_feedback",
        "ace_ct_inspired",
        "versioned_extension",
        "human_annotation",
    ]
    native_identifier: str = Field(min_length=1, max_length=200)
    native_path: str = Field(min_length=1, max_length=300)
    adapter_version: str = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def safe_reference(self) -> Self:
        if not _SAFE_IDENTIFIER.fullmatch(self.native_identifier):
            raise ValueError("Source native_identifier contains unsafe characters.")
        if not _SAFE_SOURCE_PATH.fullmatch(self.native_path):
            raise ValueError("Source native_path is not a safe field reference.")
        lowered_parts = set(re.split(r"[.\[\]-]+", self.native_path.lower()))
        if lowered_parts & _PRIVATE_PATH_PARTS:
            raise ValueError("Source references cannot name private identity fields.")
        return self


class ProjectionProvenance(StrictModel):
    method: Literal[
        "deterministic_adapter",
        "native_model",
        "native_rule",
        "human_correction",
        "human_annotation",
    ]
    provider: str | None = Field(default=None, max_length=50)
    model_identifier: str | None = Field(default=None, max_length=200)


class SpanAnnotation(StrictModel):
    prediction_id: str = Field(pattern=r"^span_[0-9a-f]{40}$")
    framework_identifier: str = Field(min_length=1, max_length=100)
    projection_type: Literal["span_annotation"] = "span_annotation"
    turn_number: int = Field(strict=True, ge=1)
    start_offset: int = Field(strict=True, ge=0)
    end_offset: int = Field(strict=True, ge=0)
    quoted_text: str
    label: str = Field(min_length=1, max_length=100)
    dimension: str | None = Field(default=None, max_length=100)
    subtype: str | None = Field(default=None, max_length=100)
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    source_reference: SourceReference
    provenance: ProjectionProvenance | None = None

    @model_validator(mode="after")
    def ordered_offsets(self) -> Self:
        if self.end_offset <= self.start_offset:
            raise ValueError("Span end_offset must be greater than start_offset.")
        return self


class TurnLabel(StrictModel):
    prediction_id: str = Field(pattern=r"^turn_[0-9a-f]{40}$")
    framework_identifier: str = Field(min_length=1, max_length=100)
    projection_type: Literal["turn_label"] = "turn_label"
    turn_number: int = Field(strict=True, ge=1)
    label: str = Field(min_length=1, max_length=100)
    dimension: str | None = Field(default=None, max_length=100)
    subtype: str | None = Field(default=None, max_length=100)
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    evidence_text: str | None = Field(default=None, max_length=1_000)
    source_reference: SourceReference
    provenance: ProjectionProvenance | None = None


class ProjectedRelation(StrictModel):
    relation_id: str = Field(pattern=r"^relation_[0-9a-f]{40}$")
    framework_identifier: str = Field(min_length=1, max_length=100)
    projection_type: Literal["relation"] = "relation"
    source_annotation_id: str = Field(pattern=r"^span_[0-9a-f]{40}$")
    target_annotation_id: str = Field(pattern=r"^span_[0-9a-f]{40}$")
    relation_type: str = Field(min_length=1, max_length=100)
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    source_reference: SourceReference
    provenance: ProjectionProvenance | None = None


class DimensionRating(StrictModel):
    rating_id: str = Field(pattern=r"^rating_[0-9a-f]{40}$")
    framework_identifier: str = Field(min_length=1, max_length=100)
    projection_type: Literal["dimension_rating"] = "dimension_rating"
    dimension_identifier: str = Field(min_length=1, max_length=100)
    domain_identifier: str | None = Field(default=None, max_length=100)
    score: float | None = Field(default=None, allow_inf_nan=False)
    scale_minimum: float = Field(allow_inf_nan=False)
    scale_maximum: float = Field(allow_inf_nan=False)
    score_status: Literal["available", "insufficient_evidence", "not_assessable"]
    assessability: Literal["text_assessable", "partially_assessable", "not_assessable"]
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    evidence_turns: tuple[int, ...] = ()
    rationale: str = Field(min_length=1, max_length=1_000)
    source_reference: SourceReference
    provenance: ProjectionProvenance | None = None

    @model_validator(mode="after")
    def validate_rating(self) -> Self:
        if self.scale_maximum <= self.scale_minimum:
            raise ValueError("Rating scale_maximum must exceed scale_minimum.")
        if self.score_status == "available":
            if self.score is None:
                raise ValueError("An available rating requires a score.")
            if not self.scale_minimum <= self.score <= self.scale_maximum:
                raise ValueError("Rating score lies outside its declared scale.")
        elif self.score is not None:
            raise ValueError("An unavailable rating must have an explicit null score.")
        if tuple(sorted(set(self.evidence_turns))) != self.evidence_turns or any(
            number < 1 for number in self.evidence_turns
        ):
            raise ValueError("Rating evidence turns must be positive, unique, and sorted.")
        return self


class GlobalMetric(StrictModel):
    metric_id: str = Field(pattern=r"^metric_[0-9a-f]{40}$")
    framework_identifier: str = Field(min_length=1, max_length=100)
    projection_type: Literal["global_metric"] = "global_metric"
    metric_name: str = Field(min_length=1, max_length=100)
    value: float | None = Field(default=None, allow_inf_nan=False)
    value_status: Literal["available", "unavailable"]
    unit_or_scale: str = Field(min_length=1, max_length=100)
    source_label: str = Field(min_length=1, max_length=200)
    comparability_statement: str = Field(min_length=1, max_length=500)
    source_reference: SourceReference
    provenance: ProjectionProvenance | None = None

    @model_validator(mode="after")
    def validate_value_status(self) -> Self:
        if (self.value_status == "available") != (self.value is not None):
            raise ValueError("Metric value and availability status are inconsistent.")
        return self


class ResearchFinding(StrictModel):
    finding_id: str = Field(pattern=r"^finding_[0-9a-f]{40}$")
    framework_identifier: str = Field(min_length=1, max_length=100)
    projection_type: Literal["finding"] = "finding"
    finding_type: Literal[
        "strength", "improvement", "missed_opportunity", "warning", "general_observation"
    ]
    description: str = Field(min_length=1, max_length=2_000)
    evidence_turns: tuple[int, ...] = ()
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    source_reference: SourceReference
    provenance: ProjectionProvenance | None = None

    @field_validator("evidence_turns")
    @classmethod
    def valid_evidence_turns(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if tuple(sorted(set(value))) != value or any(number < 1 for number in value):
            raise ValueError("Finding evidence turns must be positive, unique, and sorted.")
        return value


class ResearchLimitation(StrictModel):
    limitation_id: str = Field(pattern=r"^limitation_[0-9a-f]{40}$")
    framework_identifier: str = Field(min_length=1, max_length=100)
    projection_type: Literal["limitation"] = "limitation"
    code: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,99}$")
    description: str = Field(min_length=1, max_length=1_000)
    affected_outputs: tuple[str, ...]
    severity_or_scope: Literal["output", "framework", "run"]
    source_label: str = Field(min_length=1, max_length=200)
    source_reference: SourceReference
    provenance: ProjectionProvenance | None = None


class ResearchProjection(StrictModel):
    projection_version: Literal["1.0"] = "1.0"
    spans: tuple[SpanAnnotation, ...] = ()
    turn_labels: tuple[TurnLabel, ...] = ()
    relations: tuple[ProjectedRelation, ...] = ()
    dimension_ratings: tuple[DimensionRating, ...] = ()
    global_metrics: tuple[GlobalMetric, ...] = ()
    findings: tuple[ResearchFinding, ...] = ()
    limitations: tuple[ResearchLimitation, ...] = ()

    @model_validator(mode="after")
    def validate_identifiers_and_relations(self) -> Self:
        collections = (
            [item.prediction_id for item in self.spans],
            [item.prediction_id for item in self.turn_labels],
            [item.relation_id for item in self.relations],
            [item.rating_id for item in self.dimension_ratings],
            [item.metric_id for item in self.global_metrics],
            [item.finding_id for item in self.findings],
            [item.limitation_id for item in self.limitations],
        )
        identifiers = [identifier for group in collections for identifier in group]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Projected object identifiers must be unique.")
        span_ids = {span.prediction_id for span in self.spans}
        for relation in self.relations:
            if relation.source_annotation_id not in span_ids:
                raise ValueError("Projected relation source endpoint does not exist.")
            if relation.target_annotation_id not in span_ids:
                raise ValueError("Projected relation target endpoint does not exist.")
        return self


class OutputCapabilities(StrictModel):
    character_spans: bool
    turn_labels: bool
    relations: bool
    dimension_ratings: bool
    global_metrics: bool
    narrative_findings: bool
    evidence_turns: bool
    framework_native_view: bool
    live_execution: bool


class AnnotationOperationCapabilities(StrictModel):
    confirm: bool = False
    reject: bool = False
    change_label: bool = False
    change_dimension: bool = False
    adjust_span: bool = False
    change_rating: bool = False
    mark_insufficient_evidence: bool = False
    change_evidence: bool = False
    change_assessability: bool = False
    add_annotation: bool = False
    add_relation: bool = False


class ProjectionAnnotationCapabilities(StrictModel):
    span_annotation: AnnotationOperationCapabilities = Field(
        default_factory=AnnotationOperationCapabilities
    )
    turn_label: AnnotationOperationCapabilities = Field(
        default_factory=AnnotationOperationCapabilities
    )
    relation: AnnotationOperationCapabilities = Field(
        default_factory=AnnotationOperationCapabilities
    )
    dimension_rating: AnnotationOperationCapabilities = Field(
        default_factory=AnnotationOperationCapabilities
    )
    finding: AnnotationOperationCapabilities = Field(
        default_factory=AnnotationOperationCapabilities
    )


class ResearchCapabilities(StrictModel):
    outputs: OutputCapabilities
    annotation_operations: AnnotationOperationCapabilities = Field(
        default_factory=AnnotationOperationCapabilities
    )
    annotation_by_projection: ProjectionAnnotationCapabilities = Field(
        default_factory=ProjectionAnnotationCapabilities
    )


class ResearchTranscriptIdentity(StrictModel):
    canonical_transcript_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    transcript_projection_version: Literal["apex-canonical-v1"] = (
        TRANSCRIPT_PROJECTION_VERSION
    )
    turn_count: int = Field(strict=True, ge=0)
    role_convention: Literal["user=clinician;assistant=patient"] = (
        "user=clinician;assistant=patient"
    )
    raw_transcript_included: bool


class ResearchRunMetadata(StrictModel):
    run_id: str = Field(pattern=r"^run_[0-9a-f]{40}$")
    timestamp: str = Field(min_length=20, max_length=40)
    runtime_ms: float = Field(ge=0, allow_inf_nan=False)
    execution_mode: Literal["offline", "live"]
    completion_status: Literal["success", "failed", "refused"]
    failure_category: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_failure_category(self) -> Self:
        if self.completion_status == "success" and self.failure_category is not None:
            raise ValueError("Successful runs cannot have a failure category.")
        if self.completion_status != "success" and not self.failure_category:
            raise ValueError("Failed or refused runs require a failure category.")
        return self


class ResearchEvaluatorMetadata(StrictModel):
    identifier: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,99}$")
    display_name: str = Field(min_length=1, max_length=150)
    version: str = Field(min_length=1, max_length=50)
    evaluator_type: Literal["rule_based", "hybrid_llm", "experimental_rubric_llm"]
    provider: str | None = Field(default=None, max_length=50)
    model_identifier: str | None = Field(default=None, max_length=200)


class ResearchFrameworkMetadata(StrictModel):
    identifier: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,99}$")
    display_name: str = Field(min_length=1, max_length=150)
    version: str = Field(min_length=1, max_length=50)
    rubric_version: str | None = Field(default=None, max_length=50)
    validation_status: str = Field(min_length=1, max_length=100)
    framework_statement: str = Field(min_length=1, max_length=500)


class ResearchAdapterMetadata(StrictModel):
    identifier: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,99}$")
    version: str = Field(min_length=1, max_length=50)
    supported_native_type: Literal["apex_feedback", "ace_ct_inspired", "versioned_extension"]


class SanitizedResearchError(StrictModel):
    category: Literal[
        "evaluation_failed",
        "unexpected_error",
        "live_execution_refused",
        "invalid_native_result",
        "invalid_projection",
        "invalid_adapter_result",
        "evaluator_unavailable",
    ]
    message: str = Field(min_length=1, max_length=300)


class ResearchProvenance(StrictModel):
    generated_at: str = Field(min_length=20, max_length=40)
    runtime_ms: float = Field(ge=0, allow_inf_nan=False)
    live_execution: bool
    transcript_hash_algorithm: Literal["sha256"] = "sha256"
    identifier_hash_algorithm: Literal["sha256-truncated-160"] = "sha256-truncated-160"


class ResearchEvaluationEnvelope(StrictModel):
    schema_version: Literal["1.0"] = RESEARCH_SCHEMA_VERSION
    run: ResearchRunMetadata
    transcript: ResearchTranscriptIdentity
    evaluator: ResearchEvaluatorMetadata
    framework: ResearchFrameworkMetadata
    adapter: ResearchAdapterMetadata
    capabilities: ResearchCapabilities
    framework_result: FrameworkNativeResult | None = None
    projection: ResearchProjection
    warnings: tuple[str, ...] = ()
    status: Literal["success", "failed", "refused"]
    error: SanitizedResearchError | None = None
    provenance: ResearchProvenance

    @model_validator(mode="after")
    def validate_envelope_state(self) -> Self:
        if self.status != self.run.completion_status:
            raise ValueError("Envelope and run status must match.")
        if self.status == "success":
            if self.framework_result is None or self.error is not None:
                raise ValueError("Successful envelopes require a native result and no error.")
            if self.framework_result.native_type != self.adapter.supported_native_type:
                raise ValueError("Adapter/native result types do not match.")
        elif self.error is None or self.framework_result is not None:
            raise ValueError("Failed/refused envelopes require an error and no native result.")
        if self.provenance.runtime_ms != self.run.runtime_ms:
            raise ValueError("Run and provenance runtime must match.")
        if self.provenance.live_execution != (self.run.execution_mode == "live"):
            raise ValueError("Run and provenance execution modes must match.")
        return self


class ResearchTranscriptTurn(StrictModel):
    turn_number: int = Field(strict=True, ge=1)
    role: Literal["clinician", "patient"]
    source_role: Literal["user", "assistant"]
    text: str

    @model_validator(mode="after")
    def matching_role(self) -> Self:
        expected = "clinician" if self.source_role == "user" else "patient"
        if self.role != expected:
            raise ValueError("Transcript role and source role do not match.")
        return self


class ResearchEvaluationRequest(StrictModel):
    evaluator_identifiers: tuple[str, ...] = ("baseline",)
    allow_live: bool = False
    provider: Literal["openai", "gemini"] | None = None
    model_identifier: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        if not self.evaluator_identifiers or len(self.evaluator_identifiers) > 4:
            raise ValueError("Select between one and four research evaluators.")
        if len(set(self.evaluator_identifiers)) != len(self.evaluator_identifiers):
            raise ValueError("Research evaluator identifiers must be unique.")
        if not self.allow_live and (self.provider is not None or self.model_identifier is not None):
            raise ValueError("Provider/model overrides require allow_live=true.")
        return self


class ResearchEvaluationResponse(StrictModel):
    schema_version: Literal["1.0"] = RESEARCH_SCHEMA_VERSION
    transcript: ResearchTranscriptIdentity
    transcript_turns: tuple[ResearchTranscriptTurn, ...]
    results: tuple[ResearchEvaluationEnvelope, ...]

    @model_validator(mode="after")
    def consistent_transcript(self) -> Self:
        if len(self.transcript_turns) != self.transcript.turn_count:
            raise ValueError("Transcript identity turn count does not match returned turns.")
        if any(result.transcript.canonical_transcript_hash != self.transcript.canonical_transcript_hash for result in self.results):
            raise ValueError("All research results must use the response transcript identity.")
        return self


class ResearchEvaluatorDescriptor(StrictModel):
    identifier: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,99}$")
    display_name: str = Field(min_length=1, max_length=150)
    version: str = Field(min_length=1, max_length=50)
    framework: ResearchFrameworkMetadata
    adapter: ResearchAdapterMetadata
    capabilities: ResearchCapabilities
    requires_live_execution: bool
    supported_providers: tuple[Literal["openai", "gemini"], ...] = ()
    default_selected: bool = False
    availability: Literal["available", "server_live_disabled", "experimental_disabled"]
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_live_descriptor(self) -> Self:
        if self.requires_live_execution != self.capabilities.outputs.live_execution:
            raise ValueError("Descriptor live fields must agree.")
        if self.requires_live_execution and not self.supported_providers:
            raise ValueError("Live evaluators must declare supported providers.")
        if not self.requires_live_execution and self.supported_providers:
            raise ValueError("Offline evaluators cannot declare live providers.")
        return self


class ResearchEvaluatorDescriptorsResponse(StrictModel):
    schema_version: Literal["1.0"] = RESEARCH_SCHEMA_VERSION
    evaluators: tuple[ResearchEvaluatorDescriptor, ...]


class ResearchExportRequest(StrictModel):
    profile: Literal["full", "framework_native", "projection", "tabular"]
    envelopes: tuple[ResearchEvaluationEnvelope, ...] = Field(min_length=1, max_length=4)
    include_transcript_content: Literal[False] = False


def validate_projection_against_transcript(
    projection: ResearchProjection,
    transcript_turns: tuple[ResearchTranscriptTurn, ...],
) -> None:
    """Validate turn references, roles, span bounds, and exact quoted text."""

    turn_by_number = {turn.turn_number: turn for turn in transcript_turns}
    if len(turn_by_number) != len(transcript_turns):
        raise ValueError("Canonical transcript turn numbers must be unique.")
    valid_turns = set(turn_by_number)

    for span in projection.spans:
        turn = turn_by_number.get(span.turn_number)
        if turn is None:
            raise ValueError("Projected span references an unknown transcript turn.")
        if span.end_offset > len(turn.text):
            raise ValueError("Projected span end offset exceeds the transcript turn text.")
        if turn.text[span.start_offset : span.end_offset] != span.quoted_text:
            raise ValueError("Projected span quoted text does not match its offsets.")

    referenced_turns = [label.turn_number for label in projection.turn_labels]
    referenced_turns.extend(
        turn for rating in projection.dimension_ratings for turn in rating.evidence_turns
    )
    referenced_turns.extend(
        turn for finding in projection.findings for turn in finding.evidence_turns
    )
    if any(turn not in valid_turns for turn in referenced_turns):
        raise ValueError("Projected evidence references an unknown transcript turn.")

    if any(turn.role not in {"clinician", "patient"} for turn in transcript_turns):
        raise ValueError("Transcript contains an unknown research role attribution.")
