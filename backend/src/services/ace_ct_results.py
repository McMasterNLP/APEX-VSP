"""Deterministic framework-result construction for ACE-CT-inspired output."""

from __future__ import annotations

from domain.models.evaluator_comparison import (
    EvaluatorFrameworkAssessabilityCounts,
    EvaluatorFrameworkResults,
)
from schemas.ace_ct import ACECTAssessability, ACECTEvaluationResult


def build_ace_ct_framework_results(
    evaluation: ACECTEvaluationResult,
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
            "compatibility_scores": evaluation.score_sources.compatibility_scores,
        },
        limitations=evaluation.limitations,
    )
