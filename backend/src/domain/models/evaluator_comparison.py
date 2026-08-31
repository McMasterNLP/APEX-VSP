"""Schemas for privacy-safe, non-persisting evaluator comparisons."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


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
