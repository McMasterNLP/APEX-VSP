"""Schemas for privacy-safe, non-persisting evaluator comparisons."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from domain.models.scoring import ComputedFeedback
from schemas.ace_ct import (
    ACECTDimensionResult,
    ACECTDomainScore,
    ACECTEvaluationLimitations,
    ACECTRubricApprovalStatus,
)


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
    evaluator_type: Literal["rule_based", "hybrid_llm", "experimental_rubric_llm"]
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


class EvaluatorFrameworkAssessabilityCounts(BaseModel):
    """Dimension availability counts retained in framework artifacts."""

    text_assessable: int = Field(strict=True, ge=0, le=11)
    partially_assessable: int = Field(strict=True, ge=0, le=11)
    not_assessable: int = Field(strict=True, ge=0, le=11)
    scored: int = Field(strict=True, ge=0, le=11)
    insufficient_evidence: int = Field(strict=True, ge=0, le=11)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_totals(self) -> Self:
        if self.text_assessable + self.partially_assessable + self.not_assessable != 11:
            raise ValueError("Framework assessability counts must total 11 dimensions.")
        if self.scored + self.insufficient_evidence != 11:
            raise ValueError("Framework score availability counts must total 11 dimensions.")
        return self


class EvaluatorFrameworkResults(BaseModel):
    """First-class framework output preserved independently of APEX compatibility scores."""

    framework: Literal["ACE-CT-inspired"]
    implementation_type: Literal["experimental_transcript_rubric"]
    validation_status: Literal["experimental_unvalidated"]
    publication_reproduction: Literal[False]
    rubric_version: str = Field(min_length=1, max_length=50)
    approval_status: ACECTRubricApprovalStatus
    dimension_results: tuple[ACECTDimensionResult, ...]
    domain_scores: tuple[ACECTDomainScore, ...]
    assessability_counts: EvaluatorFrameworkAssessabilityCounts
    score_sources: dict[str, str]
    limitations: ACECTEvaluationLimitations

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_complete_framework(self) -> Self:
        if len(self.dimension_results) != 11:
            raise ValueError("Framework results must contain exactly 11 dimension results.")
        if len(self.domain_scores) != 4:
            raise ValueError("Framework results must contain exactly four domain scores.")
        if not self.score_sources or any(
            not key.strip() or not value.strip() or len(key) > 100 or len(value) > 200
            for key, value in self.score_sources.items()
        ):
            raise ValueError("Framework score sources must be non-empty bounded labels.")
        return self


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
    framework_results: EvaluatorFrameworkResults | None = None
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
    framework_results: EvaluatorFrameworkResults | None = None
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


class SeededCaseStudyArtifact(BaseModel):
    """Sanitized aggregate for the four public seeded transcript conditions."""

    schema_version: str
    generated_at: str
    git_commit: str | None = None
    study_type: Literal["technical_evaluator_case_study"]
    requested_evaluators: list[str]
    condition_results: dict[str, EvaluatorComparisonArtifact]
    paper_table_rows: list[dict]
    methodology_notes: list[str]
    limitations: list[str]

    model_config = ConfigDict(frozen=True)
