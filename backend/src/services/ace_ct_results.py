"""Deterministic framework-result construction for ACE-CT-inspired output."""

from __future__ import annotations

import math

from domain.models.evaluator_comparison import (
    ACECTCompatibilityProjection,
    ACECTCompatibilityScoreSources,
    EvaluatorFrameworkAssessabilityCounts,
    EvaluatorFrameworkResults,
    EvaluatorScores,
)
from schemas.ace_ct import (
    ACECTAssessability,
    ACECTDimensionId,
    ACECTDimensionResult,
    ACECTDomain,
    ACECTDomainScore,
    ACECTEvaluationResult,
)

FRAMEWORK_EQUIVALENCE_WARNING = (
    "Canonical APEX compatibility score differences are not framework-equivalent and must not "
    "be interpreted as clinical validity or direct ACE-CT agreement."
)


def normalize_ace_ct_score(score: int | None) -> float | None:
    """Map a native integer 1-5 score to 0-100 without imputation."""

    if score is None:
        return None
    if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 5:
        raise ValueError("ACE-CT-inspired score must be an integer from 1 through 5 or null.")
    return ((score - 1) / 4) * 100.0


def aggregate_ace_ct_domains(
    dimension_results: tuple[ACECTDimensionResult, ...],
) -> tuple[ACECTDomainScore, ...]:
    """Calculate native-scale unweighted domain means, excluding null scores."""

    aggregates: list[ACECTDomainScore] = []
    for domain in ACECTDomain:
        members = [result for result in dimension_results if result.domain == domain]
        scores = [result.score for result in members if result.score is not None]
        aggregates.append(
            ACECTDomainScore(
                domain=domain,
                mean_score=math.fsum(scores) / len(scores) if scores else None,
                scored_dimension_count=len(scores),
                insufficient_evidence_count=len(members) - len(scores),
            )
        )
    return tuple(aggregates)


def project_ace_ct_compatibility_scores(
    evaluation: ACECTEvaluationResult,
    *,
    apex_baseline_spikes_completion_score: float | None = None,
) -> ACECTCompatibilityProjection:
    """Project validated dimensions into explicitly non-equivalent APEX score fields."""

    if apex_baseline_spikes_completion_score is not None:
        if (
            isinstance(apex_baseline_spikes_completion_score, bool)
            or not isinstance(apex_baseline_spikes_completion_score, (int, float))
            or not math.isfinite(apex_baseline_spikes_completion_score)
            or not 0 <= apex_baseline_spikes_completion_score <= 100
        ):
            raise ValueError("APEX baseline SPIKES score must be finite from 0 through 100.")

    normalized_by_dimension = {
        result.dimension_id: normalize_ace_ct_score(result.score)
        for result in evaluation.dimension_results
    }
    assessable_scores = [score for score in normalized_by_dimension.values() if score is not None]
    normalized_mean = (
        math.fsum(assessable_scores) / len(assessable_scores) if assessable_scores else None
    )
    empathy_score = normalized_by_dimension[ACECTDimensionId.RESPOND_TO_EMOTION]

    return ACECTCompatibilityProjection(
        scores=EvaluatorScores(
            empathy_score=empathy_score,
            communication_score=normalized_mean,
            spikes_completion_score=(
                float(apex_baseline_spikes_completion_score)
                if apex_baseline_spikes_completion_score is not None
                else None
            ),
            overall_score=normalized_mean,
        ),
        score_sources=ACECTCompatibilityScoreSources(
            empathy_score=("ace_ct_inspired.dimension.respond_to_emotion.normalized_0_100"),
            communication_score=("ace_ct_inspired.mean_of_non_null_dimensions.normalized_0_100"),
            overall_score=("ace_ct_inspired.mean_of_non_null_dimensions.normalized_0_100"),
            spikes_completion_score=(
                "apex_baseline.spikes_completion_score_not_ace_ct"
                if apex_baseline_spikes_completion_score is not None
                else "unavailable_no_apex_baseline_spikes_score"
            ),
        ),
        warnings=(FRAMEWORK_EQUIVALENCE_WARNING,),
    )


def build_ace_ct_framework_results(
    evaluation: ACECTEvaluationResult,
    *,
    compatibility_projection: ACECTCompatibilityProjection | None = None,
) -> EvaluatorFrameworkResults:
    """Promote validated model output into first-class comparison results."""

    assessability = [result.assessability for result in evaluation.dimension_results]
    scored = sum(result.score is not None for result in evaluation.dimension_results)
    return EvaluatorFrameworkResults(
        framework=evaluation.framework_name,
        implementation_type=evaluation.implementation_type,
        validation_status=evaluation.validation_status,
        publication_reproduction=evaluation.publication_reproduction,
        rubric_version=evaluation.rubric_version,
        approval_status=evaluation.approval_status,
        dimension_results=evaluation.dimension_results,
        domain_scores=evaluation.domain_scores,
        assessability_counts=EvaluatorFrameworkAssessabilityCounts(
            text_assessable=assessability.count(ACECTAssessability.TEXT_ASSESSABLE),
            partially_assessable=assessability.count(ACECTAssessability.PARTIALLY_ASSESSABLE),
            not_assessable=assessability.count(ACECTAssessability.NOT_ASSESSABLE),
            scored=scored,
            insufficient_evidence=len(evaluation.dimension_results) - scored,
        ),
        score_sources={
            "dimension_scores": evaluation.score_sources.dimension_scores,
            "domain_scores": evaluation.score_sources.domain_scores,
            **(
                {
                    f"compatibility.{field}": source
                    for field, source in compatibility_projection.score_sources.model_dump().items()
                }
                if compatibility_projection is not None
                else {
                    "compatibility_scores": evaluation.score_sources.compatibility_scores,
                }
            ),
        },
        limitations=evaluation.limitations,
    )
