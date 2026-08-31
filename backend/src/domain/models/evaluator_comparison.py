"""Schemas for privacy-safe, non-persisting evaluator comparisons."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

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
