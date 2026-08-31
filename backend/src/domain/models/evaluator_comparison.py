"""Schemas for privacy-safe, non-persisting evaluator comparisons."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from domain.models.scoring import ComputedFeedback


class CanonicalTranscriptTurn(BaseModel):
    """Minimal turn representation used for deterministic transcript hashing."""

    turn_number: int
    role: str
    text: str

    model_config = ConfigDict(frozen=True)


class EvaluatorProvenance(BaseModel):
    """Public implementation metadata safe to include in comparison artifacts."""

    evaluator_identifier: str
    plugin_identifier: str
    class_name: str
    version: str
    evaluator_type: Literal["rule_based", "hybrid_llm"]
    llm_provider: str | None = None
    model_identifier: str | None = None
    reviewer_version: str | None = None
    prompt_version: str | None = None

    model_config = ConfigDict(frozen=True)


class EvaluatorScores(BaseModel):
    """Normalized evaluator scores used by comparison analysis and exports."""

    empathy_score: float | None = None
    communication_score: float | None = None
    spikes_completion_score: float | None = None
    overall_score: float | None = None

    model_config = ConfigDict(frozen=True)


class SanitizedEvaluatorError(BaseModel):
    """Allowlisted failure detail that never contains a raw exception."""

    category: Literal["evaluation_failed", "unexpected_error"]
    message: str

    model_config = ConfigDict(frozen=True)


class EvaluatorRunResult(BaseModel):
    """Independent in-memory result for one evaluator invocation."""

    evaluator_identifier: str
    evaluator_name: str
    evaluator_version: str
    status: Literal["success", "failed"]
    runtime_ms: float
    transcript_hash: str
    provenance: EvaluatorProvenance
    scores: EvaluatorScores | None = None
    structured_feedback: ComputedFeedback | None = None
    error: SanitizedEvaluatorError | None = None

    model_config = ConfigDict(frozen=True)


class NumericMetricSummary(BaseModel):
    """Derived distribution summary for one numeric metric."""

    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    range: float | None = None
    available_count: int
    missing_evaluators: list[str]

    model_config = ConfigDict(frozen=True)


class PairwiseEvaluatorDifference(BaseModel):
    """Signed A-minus-B score and runtime differences for one evaluator pair."""

    evaluator_a: str
    evaluator_b: str
    evaluator_a_status: Literal["success", "failed"]
    evaluator_b_status: Literal["success", "failed"]
    score_differences: dict[str, float | None]
    runtime_difference_ms: float

    model_config = ConfigDict(frozen=True)


class PairwiseFindingAgreement(BaseModel):
    """Set agreement for comparable stage or turn-linked evidence findings."""

    evaluator_a: str
    evaluator_b: str
    comparable: bool
    intersection_count: int | None = None
    union_count: int | None = None
    jaccard: float | None = None
    shared: list[str] = Field(default_factory=list)
    only_a: list[str] = Field(default_factory=list)
    only_b: list[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class EvaluatorComparisonAnalysis(BaseModel):
    """Deterministic summaries derived from observed evaluator run results."""

    successful_evaluator_count: int
    failed_evaluator_count: int
    score_metrics: dict[str, NumericMetricSummary]
    runtime: NumericMetricSummary
    pairwise_differences: list[PairwiseEvaluatorDifference]
    spikes_stage_agreement: list[PairwiseFindingAgreement]
    evidence_agreement: list[PairwiseFindingAgreement]
    unique_findings: dict[str, list[str]]
    limitations: list[str]

    model_config = ConfigDict(frozen=True)


class SanitizedEvidenceFinding(BaseModel):
    """Turn-linked evidence metadata with transcript text deliberately excluded."""

    finding_type: str
    turn_number: int | None = None
    dimension: str | None = None
    subtype: str | None = None
    confidence: float | None = None

    model_config = ConfigDict(frozen=True)


class SanitizedFeedbackSummary(BaseModel):
    """Privacy-safe feedback fields suitable for canonical artifacts."""

    spikes_coverage: dict | None = None
    strengths: str | None = None
    areas_for_improvement: str | None = None
    missed_opportunities: list[SanitizedEvidenceFinding] = Field(default_factory=list)
    evidence: list[SanitizedEvidenceFinding] = Field(default_factory=list)
    linkage_stats: dict | None = None
    question_breakdown: dict | None = None

    model_config = ConfigDict(frozen=True)


class EvaluatorArtifactResult(BaseModel):
    """Privacy-safe observed result written to comparison artifacts."""

    evaluator_identifier: str
    evaluator_name: str
    evaluator_version: str
    status: Literal["success", "failed"]
    runtime_ms: float
    transcript_hash: str
    provenance: EvaluatorProvenance
    scores: EvaluatorScores | None = None
    feedback: SanitizedFeedbackSummary | None = None
    error: SanitizedEvaluatorError | None = None

    model_config = ConfigDict(frozen=True)


class EvaluatorComparisonArtifact(BaseModel):
    """Canonical JSON document for one local evaluator comparison run."""

    schema_version: str
    run_id: str
    generated_at: str
    git_commit: str | None = None
    anonymized_session_id: str
    transcript_hash: str
    requested_evaluators: list[str]
    evaluator_provenance: list[EvaluatorProvenance]
    observed_results: list[EvaluatorArtifactResult]
    derived_analysis: EvaluatorComparisonAnalysis
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    canonical_transcript: list[CanonicalTranscriptTurn] | None = None

    model_config = ConfigDict(frozen=True)
