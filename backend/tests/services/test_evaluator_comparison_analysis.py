"""Tests for deterministic evaluator comparison analysis."""

from __future__ import annotations

from domain.models.evaluator_comparison import (
    EvaluatorRunResult,
    EvaluatorScores,
    SanitizedEvaluatorError,
)
from domain.models.scoring import ComputedFeedback
from services.evaluator_comparison_service import (
    analyze_evaluator_results,
    build_evaluator_provenance,
)


def _feedback(
    identifier: str,
    score: float,
    *,
    stages: list[str] | None = None,
    missed_turns: list[int] | None = None,
    evidence_turns: list[int] | None = None,
) -> ComputedFeedback:
    return ComputedFeedback(
        session_id=7,
        empathy_score=score,
        communication_score=score + 1,
        spikes_completion_score=score + 2,
        overall_score=score + 3,
        eo_counts_by_dimension={},
        elicitation_counts_by_type={},
        response_counts_by_type={},
        missed_opportunities=[{"turn_number": turn_number} for turn_number in (missed_turns or [])],
        eo_spans=[
            {"turn_number": turn_number, "dimension": "Feeling"}
            for turn_number in (evidence_turns or [])
        ],
        elicitation_spans=[],
        response_spans=[],
        spikes_coverage={"covered": stages or [], "percent": 0.0},
        question_breakdown={},
        evaluator_meta={"phase": identifier},
        latency_ms_avg=0.0,
    )


def _success(
    identifier: str,
    score: float,
    runtime_ms: float,
    **feedback_kwargs,
) -> EvaluatorRunResult:
    feedback = _feedback(identifier, score, **feedback_kwargs)
    return EvaluatorRunResult(
        evaluator_identifier=identifier,
        evaluator_name=identifier,
        evaluator_version="1.0",
        status="success",
        runtime_ms=runtime_ms,
        transcript_hash="a" * 64,
        provenance=build_evaluator_provenance(identifier),
        scores=EvaluatorScores(
            empathy_score=feedback.empathy_score,
            communication_score=feedback.communication_score,
            spikes_completion_score=feedback.spikes_completion_score,
            overall_score=feedback.overall_score,
        ),
        structured_feedback=feedback,
    )


def _failure(identifier: str, runtime_ms: float) -> EvaluatorRunResult:
    provenance = build_evaluator_provenance(identifier)
    return EvaluatorRunResult(
        evaluator_identifier=identifier,
        evaluator_name=provenance.class_name,
        evaluator_version=provenance.version,
        status="failed",
        runtime_ms=runtime_ms,
        transcript_hash="a" * 64,
        provenance=provenance,
        error=SanitizedEvaluatorError(
            category="evaluation_failed",
            message="Evaluation failed.",
        ),
    )


def test_complete_results_include_numeric_pairwise_and_agreement_analysis() -> None:
    results = [
        _success(
            "baseline",
            10.0,
            5.0,
            stages=["perception", "emotion"],
            missed_turns=[2],
            evidence_turns=[2],
        ),
        _success(
            "hybrid_v1",
            20.0,
            15.0,
            stages=["emotion", "strategy"],
            missed_turns=[2, 4],
            evidence_turns=[2, 4],
        ),
        _success(
            "hybrid_v2",
            30.0,
            25.0,
            stages=["emotion"],
            missed_turns=[4],
            evidence_turns=[4, 6],
        ),
    ]

    analysis = analyze_evaluator_results(results)

    empathy = analysis.score_metrics["empathy_score"]
    assert empathy.minimum == 10.0
    assert empathy.maximum == 30.0
    assert empathy.mean == 20.0
    assert empathy.range == 20.0
    assert empathy.available_count == 3
    assert analysis.runtime.mean == 15.0
    assert analysis.successful_evaluator_count == 3
    assert analysis.failed_evaluator_count == 0
    assert len(analysis.pairwise_differences) == 3
    assert analysis.pairwise_differences[0].score_differences["empathy_score"] == -10.0
    assert analysis.pairwise_differences[0].runtime_difference_ms == -10.0
    assert analysis.spikes_stage_agreement[0].jaccard == 0.3333
    assert "eo:turn:6:feeling" in analysis.unique_findings["hybrid_v2"]


def test_partial_failures_and_missing_metrics_are_explicit() -> None:
    baseline = _success("baseline", 10.0, 1.0)
    hybrid_v1 = _failure("hybrid_v1", 2.0)
    hybrid_v2 = _success("hybrid_v2", 30.0, 3.0)
    hybrid_v2 = hybrid_v2.model_copy(
        update={"scores": hybrid_v2.scores.model_copy(update={"communication_score": None})}
    )

    analysis = analyze_evaluator_results([baseline, hybrid_v1, hybrid_v2])

    assert analysis.successful_evaluator_count == 2
    assert analysis.failed_evaluator_count == 1
    assert analysis.score_metrics["empathy_score"].available_count == 2
    assert analysis.score_metrics["empathy_score"].missing_evaluators == ["hybrid_v1"]
    assert analysis.score_metrics["communication_score"].missing_evaluators == [
        "hybrid_v1",
        "hybrid_v2",
    ]
    failed_pair = analysis.pairwise_differences[0]
    assert all(value is None for value in failed_pair.score_differences.values())
    assert analysis.spikes_stage_agreement[0].comparable is False


def test_numeric_values_are_normalized_and_output_is_deterministic() -> None:
    results = [
        _success("baseline", 0.1 + 0.2, 0.00001),
        _success("hybrid_v1", 0.300049, 0.00002),
    ]

    first = analyze_evaluator_results(results)
    second = analyze_evaluator_results(results)

    assert first == second
    assert first.score_metrics["empathy_score"].minimum == 0.3
    assert first.score_metrics["empathy_score"].maximum == 0.3
    assert first.score_metrics["empathy_score"].range == 0.0
    assert first.runtime.minimum == 0.0


def test_analysis_has_no_unsupported_winner_field() -> None:
    payload = analyze_evaluator_results(
        [_success("baseline", 10.0, 1.0), _success("hybrid_v1", 20.0, 2.0)]
    ).model_dump(mode="json")

    def keys(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                yield key
                yield from keys(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from keys(nested)

    assert "winner" not in set(keys(payload))
