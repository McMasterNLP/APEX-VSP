"""Unit tests for stable evaluator comparison CSV summaries."""

from __future__ import annotations

import csv
import io

from domain.models.evaluator_comparison import (
    EvaluatorArtifactResult,
    EvaluatorComparisonArtifact,
    EvaluatorScores,
    SanitizedEvaluatorError,
)
from services.evaluator_comparison_service import (
    CSV_SUMMARY_COLUMNS,
    build_evaluator_provenance,
    render_csv_summary,
)


def _artifact() -> EvaluatorComparisonArtifact:
    success = EvaluatorArtifactResult(
        evaluator_identifier="baseline",
        evaluator_name='Baseline, "Quoted"',
        evaluator_version="1.0",
        status="success",
        runtime_ms=1.25,
        transcript_hash="a" * 64,
        provenance=build_evaluator_provenance("baseline"),
        scores=EvaluatorScores(
            empathy_score=10.0,
            communication_score=20.0,
            spikes_completion_score=30.0,
            overall_score=40.0,
        ),
    )
    failed = EvaluatorArtifactResult(
        evaluator_identifier="hybrid_v1",
        evaluator_name="ApexHybridEvaluator",
        evaluator_version="1.0",
        status="failed",
        runtime_ms=2.5,
        transcript_hash="a" * 64,
        provenance=build_evaluator_provenance("hybrid_v1"),
        error=SanitizedEvaluatorError(
            category="evaluation_failed",
            message="Safe failure.",
        ),
    )
    return EvaluatorComparisonArtifact.model_construct(
        schema_version="1.0",
        run_id="run-1",
        generated_at="2026-01-01T00:00:00Z",
        anonymized_session_id="session-safe",
        transcript_hash="a" * 64,
        requested_evaluators=["baseline", "hybrid_v1"],
        evaluator_provenance=[success.provenance, failed.provenance],
        observed_results=[success, failed],
        derived_analysis=None,
        warnings=[],
        limitations=[],
    )


def test_csv_has_stable_column_order_and_correct_escaping() -> None:
    rendered = render_csv_summary(_artifact())
    rows = list(csv.DictReader(io.StringIO(rendered)))

    assert rendered.splitlines()[0] == ",".join(CSV_SUMMARY_COLUMNS)
    assert list(rows[0]) == list(CSV_SUMMARY_COLUMNS)
    assert rows[0]["evaluator_name"] == 'Baseline, "Quoted"'
    assert rows[0]["overall_score"] == "40.0"


def test_csv_failed_rows_use_consistent_empty_score_values() -> None:
    rows = list(csv.DictReader(io.StringIO(render_csv_summary(_artifact()))))
    failed = rows[1]

    assert failed["status"] == "failed"
    assert failed["empathy_score"] == ""
    assert failed["communication_score"] == ""
    assert failed["spikes_completion_score"] == ""
    assert failed["overall_score"] == ""
    assert failed["error_category"] == "evaluation_failed"


def test_csv_never_contains_transcript_or_feedback_blob_fields() -> None:
    rendered = render_csv_summary(_artifact())

    assert "canonical_transcript" not in rendered
    assert "structured_feedback" not in rendered
    assert "evidence" not in rendered
    assert "patient_text" not in rendered
