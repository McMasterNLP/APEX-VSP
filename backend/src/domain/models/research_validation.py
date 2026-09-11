"""Item 3A: strict contracts for immutable evaluator-performance validation runs.

@remarks
Scope is deliberately narrow (see `services/research_validation/`): exactly one
matching policy (`exact_span_match`) and exactly one metric family (span
classification: precision/recall/F1, per-label + micro + macro). Every ratio is
represented as an exact reduced-fraction string (e.g. ``"3/4"``) rather than a
float, so a validation run's persisted result is byte-identical across two
creations with identical inputs.
"""

from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.time import UTCDateTime
from domain.models.research_annotation import CoverageLevel, ValidationEligibilityRecord

VALIDATION_SCHEMA_VERSION = "1.0"
SPAN_CLASSIFICATION_METRIC_IMPLEMENTATION_VERSION = "span-classification-v1"
EXACT_SPAN_MATCH_POLICY_IDENTIFIER = "exact_span_match"
EXACT_SPAN_MATCH_POLICY_VERSION = "1.0"

RatioStatus = Literal["computed", "ineligible", "no_reference_support", "no_predicted_support"]


class StrictValidationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RatioResult(StrictValidationModel):
    """One precision/recall/F1-shaped value: an exact fraction, or an explicit reason it's absent.

    @remarks
    ``value`` is a reduced fraction string (e.g. ``"3/4"``, ``"1"``, ``"0"``) and is
    non-null if and only if ``status == "computed"``. This guarantees an ineligible
    or undefined metric never silently carries a misleading number.
    """

    status: RatioStatus
    value: str | None = None
    note: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_value_presence(self) -> Self:
        if (self.status == "computed") != (self.value is not None):
            raise ValueError("A ratio value must be present only when status is 'computed'.")
        return self


class SpanLabelClassificationMetric(StrictValidationModel):
    """Per-label TP/FP/FN counts and precision/recall/F1 under one matching policy."""

    label: str = Field(min_length=1, max_length=100)
    support: int = Field(ge=0)
    predicted_count: int = Field(ge=0)
    true_positives: int = Field(ge=0)
    false_positives: int = Field(ge=0)
    false_negatives: int = Field(ge=0)
    precision: RatioResult
    recall: RatioResult
    f1: RatioResult

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.true_positives + self.false_negatives != self.support:
            raise ValueError("Label true_positives + false_negatives must equal support.")
        if self.true_positives + self.false_positives != self.predicted_count:
            raise ValueError(
                "Label true_positives + false_positives must equal predicted_count."
            )
        return self


class SpanClassificationAggregate(StrictValidationModel):
    """Micro- or macro-averaged span-classification result."""

    true_positives: int = Field(ge=0)
    false_positives: int = Field(ge=0)
    false_negatives: int = Field(ge=0)
    precision: RatioResult
    recall: RatioResult
    f1: RatioResult
    labels_included: int = Field(ge=0)


class SpanClassificationMetrics(StrictValidationModel):
    """The one implemented (span/label classification) metric family's full result."""

    metric_family: Literal["span_classification"] = "span_classification"
    metric_implementation_version: str = Field(min_length=1, max_length=100)
    matching_policy_identifier: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,99}$")
    matching_policy_version: str = Field(min_length=1, max_length=50)
    per_label: tuple[SpanLabelClassificationMetric, ...]
    micro: SpanClassificationAggregate
    macro: SpanClassificationAggregate


class ValidationRunResult(StrictValidationModel):
    """The full, reproducible computed payload persisted on a validation run.

    @remarks
    A pure function of (evaluator projection, reference projection, matching
    policy, metric implementation version): no timestamps, randomness, or
    dict-ordering-dependent accumulation may appear anywhere in this model.
    """

    schema_version: Literal["1.0"] = VALIDATION_SCHEMA_VERSION
    coverage_level: CoverageLevel
    eligibility: ValidationEligibilityRecord
    span_classification: SpanClassificationMetrics


class ValidationRunCreateRequest(StrictValidationModel):
    evaluation_run_uuid: UUID
    annotation_set_uuid: UUID
    matching_policy_identifier: str = Field(
        default=EXACT_SPAN_MATCH_POLICY_IDENTIFIER,
        pattern=r"^[a-z][a-z0-9_.-]{2,99}$",
    )


class ValidationRunRecord(StrictValidationModel):
    """The immutable, durable Item 3A validation-run record returned by the API."""

    validation_run_uuid: UUID
    evaluation_run_uuid: UUID
    annotation_set_uuid: UUID
    annotation_set_revision_at_validation: int = Field(ge=0)
    transcript_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluator_identifier: str = Field(min_length=1, max_length=100)
    evaluator_version: str = Field(min_length=1, max_length=50)
    matching_policy_identifier: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,99}$")
    matching_policy_version: str = Field(min_length=1, max_length=50)
    metric_implementation_version: str = Field(min_length=1, max_length=100)
    coverage_level: CoverageLevel
    results: ValidationRunResult
    warnings: tuple[str, ...] = ()
    created_by_reference: str
    created_at: UTCDateTime


class ValidationRunExportRequest(StrictValidationModel):
    profile: Literal["full", "results_only"] = "full"
    include_transcript_content: bool = False
