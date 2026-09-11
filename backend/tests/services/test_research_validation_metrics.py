"""Hand-computed fixture for the Item 3A exact-span-match + span-classification engine.

@remarks
This test constructs a small, fully-controlled reference span set and evaluator
projection with deliberate exact matches, false positives, false negatives, and
one label with zero reference instances -- then asserts precision/recall/F1
(per-label, micro, macro) against numbers worked out by hand as exact fractions.
No database or HTTP layer is involved; this isolates the matching/metric engine
itself from Item 1/2A/2B plumbing (covered separately in the API-level tests).
"""

from __future__ import annotations

from domain.models.research_annotation import DecisionRevisionRecord
from domain.models.research_evaluation import SourceReference, SpanAnnotation
from services.research_annotation_service import ResearchAnnotationService
from services.research_validation.exact_span_match import match_spans_exact
from services.research_validation.metrics import compute_span_classification_metrics


def _ref(native_id: str) -> SourceReference:
    return SourceReference(
        native_result_type="human_annotation",
        native_identifier=native_id,
        native_path=f"spans[{native_id}]",
        adapter_version="1.1",
    )


def _span(prediction_id_suffix: str, turn: int, start: int, end: int, label: str) -> SpanAnnotation:
    return SpanAnnotation(
        prediction_id=f"span_{prediction_id_suffix * 40}",
        framework_identifier="apex-spikes-afce",
        turn_number=turn,
        start_offset=start,
        end_offset=end,
        quoted_text="x" * (end - start),
        label=label,
        source_reference=_ref(f"pred_{prediction_id_suffix}_{turn}_{start}_{end}"),
    )


LABEL_A = "empathic_opportunity"
LABEL_B = "empathic_response"
LABEL_C = "elicitation"


def _reference_spans() -> tuple[SpanAnnotation, ...]:
    return (
        _span("1", 1, 0, 5, LABEL_A),  # ref A #1
        _span("2", 1, 10, 15, LABEL_A),  # ref A #2
        _span("3", 2, 0, 4, LABEL_A),  # ref A #3 (evaluator will miss this one -> FN)
        _span("4", 2, 5, 9, LABEL_B),  # ref B #1 (evaluator will miss this one -> FN)
    )


def _evaluator_spans() -> tuple[SpanAnnotation, ...]:
    return (
        _span("1", 1, 0, 5, LABEL_A),  # exact match of ref A #1 -> TP
        _span("2", 1, 10, 15, LABEL_A),  # exact match of ref A #2 -> TP
        _span("5", 3, 0, 5, LABEL_A),  # no reference match -> FP
        _span("6", 3, 10, 15, LABEL_C),  # label with zero reference instances -> FP, no-support
    )


def test_hand_computed_exact_span_match_and_span_classification_metrics():
    reference = _reference_spans()
    evaluator = _evaluator_spans()

    outcomes = match_spans_exact(evaluator, reference)
    outcomes_by_label = {outcome.label: outcome for outcome in outcomes}

    # Hand-computed match partition:
    #   label A: support=3 (ref #1,#2,#3), predicted=3 (#1,#2,#5); TP=2 (#1,#2 exact),
    #            FP=1 (#5 unmatched), FN=1 (ref #3 missed).
    #   label B: support=1 (ref #4), predicted=0; TP=0, FP=0, FN=1.
    #   label C: support=0, predicted=1 (#6); TP=0, FP=1, FN=0.
    assert outcomes_by_label[LABEL_A].true_positives == 2
    assert outcomes_by_label[LABEL_A].false_positives == 1
    assert outcomes_by_label[LABEL_A].false_negatives == 1
    assert outcomes_by_label[LABEL_A].support == 3
    assert outcomes_by_label[LABEL_A].predicted_count == 3

    assert outcomes_by_label[LABEL_B].true_positives == 0
    assert outcomes_by_label[LABEL_B].false_positives == 0
    assert outcomes_by_label[LABEL_B].false_negatives == 1
    assert outcomes_by_label[LABEL_B].support == 1
    assert outcomes_by_label[LABEL_B].predicted_count == 0

    assert outcomes_by_label[LABEL_C].true_positives == 0
    assert outcomes_by_label[LABEL_C].false_positives == 1
    assert outcomes_by_label[LABEL_C].false_negatives == 0
    assert outcomes_by_label[LABEL_C].support == 0
    assert outcomes_by_label[LABEL_C].predicted_count == 1

    # Reuse the real Item 2A eligibility gate: exhaustive coverage + at least one
    # reviewed instance makes span_precision/span_recall/span_f1 all eligible.
    eligibility = ResearchAnnotationService._validation_eligibility(
        "exhaustive",
        (
            DecisionRevisionRecord(
                decision_uuid="00000000-0000-0000-0000-000000000001",
                prediction_id="span_" + "1" * 40,
                projection_type="span_annotation",
                revision_number=1,
                decision="confirmed",
                reviewer_reference="reviewer_test",
                created_at="2026-01-01T00:00:00+00:00",
            ),
        ),
    )
    assert set(eligibility.eligible_metric_identifiers) >= {
        "span_precision",
        "span_recall",
        "span_f1",
    }

    metrics = compute_span_classification_metrics(
        outcomes,
        eligibility,
        metric_implementation_version="span-classification-v1",
        matching_policy_identifier="exact_span_match",
        matching_policy_version="1.0",
    )

    per_label = {item.label: item for item in metrics.per_label}

    # Hand-computed label A: precision=2/3, recall=2/3, f1=2*2/(2*2+1+1)=4/6=2/3.
    assert per_label[LABEL_A].precision.status == "computed"
    assert per_label[LABEL_A].precision.value == "2/3"
    assert per_label[LABEL_A].recall.status == "computed"
    assert per_label[LABEL_A].recall.value == "2/3"
    assert per_label[LABEL_A].f1.status == "computed"
    assert per_label[LABEL_A].f1.value == "2/3"

    # Hand-computed label B: no predictions -> precision undefined; recall=0/1=0;
    # f1=2*0/(2*0+0+1)=0.
    assert per_label[LABEL_B].precision.status == "no_predicted_support"
    assert per_label[LABEL_B].precision.value is None
    assert per_label[LABEL_B].recall.status == "computed"
    assert per_label[LABEL_B].recall.value == "0"
    assert per_label[LABEL_B].f1.status == "computed"
    assert per_label[LABEL_B].f1.value == "0"

    # Hand-computed label C: zero reference instances -> all three explicitly null,
    # never a silently misleading 0.0, even though precision alone is technically
    # computable from predictions (1 predicted, 0 matched -> 0/1).
    assert per_label[LABEL_C].support == 0
    assert per_label[LABEL_C].precision.status == "no_reference_support"
    assert per_label[LABEL_C].precision.value is None
    assert per_label[LABEL_C].recall.status == "no_reference_support"
    assert per_label[LABEL_C].recall.value is None
    assert per_label[LABEL_C].f1.status == "no_reference_support"
    assert per_label[LABEL_C].f1.value is None

    # Hand-computed micro: total TP=2, FP=1(A)+0(B)+1(C)=2, FN=1(A)+1(B)+0(C)=2.
    # micro precision = 2/(2+2) = 1/2; micro recall = 2/(2+2) = 1/2;
    # micro f1 = 2*2/(2*2+2+2) = 4/8 = 1/2.
    assert metrics.micro.true_positives == 2
    assert metrics.micro.false_positives == 2
    assert metrics.micro.false_negatives == 2
    assert metrics.micro.precision.value == "1/2"
    assert metrics.micro.recall.value == "1/2"
    assert metrics.micro.f1.value == "1/2"

    # Hand-computed macro: average only over labels with a *computed* value.
    # precision: only A is computed (2/3) -> macro precision = 2/3.
    # recall: A (2/3) and B (0) are computed, C excluded -> (2/3 + 0)/2 = 1/3.
    # f1: A (2/3) and B (0) are computed, C excluded -> (2/3 + 0)/2 = 1/3.
    assert metrics.macro.precision.value == "2/3"
    assert metrics.macro.recall.value == "1/3"
    assert metrics.macro.f1.value == "1/3"


def test_ineligible_metric_never_carries_a_number():
    """`prediction_review_only` coverage makes span_recall/span_f1 ineligible."""

    reference = _reference_spans()
    evaluator = _evaluator_spans()
    outcomes = match_spans_exact(evaluator, reference)

    eligibility = ResearchAnnotationService._validation_eligibility(
        "prediction_review_only",
        (
            DecisionRevisionRecord(
                decision_uuid="00000000-0000-0000-0000-000000000002",
                prediction_id="span_" + "1" * 40,
                projection_type="span_annotation",
                revision_number=1,
                decision="confirmed",
                reviewer_reference="reviewer_test",
                created_at="2026-01-01T00:00:00+00:00",
            ),
        ),
    )
    assert "span_precision" in eligibility.eligible_metric_identifiers
    assert "span_recall" in eligibility.ineligible_metric_identifiers
    assert "span_f1" in eligibility.ineligible_metric_identifiers

    metrics = compute_span_classification_metrics(
        outcomes,
        eligibility,
        metric_implementation_version="span-classification-v1",
        matching_policy_identifier="exact_span_match",
        matching_policy_version="1.0",
    )

    for item in metrics.per_label:
        assert item.recall.status == "ineligible"
        assert item.recall.value is None
        assert item.f1.status == "ineligible"
        assert item.f1.value is None
    assert metrics.micro.recall.status == "ineligible"
    assert metrics.micro.recall.value is None
    assert metrics.macro.f1.status == "ineligible"
    assert metrics.macro.f1.value is None
    # Precision remains eligible and numeric where support/predictions exist.
    per_label = {item.label: item for item in metrics.per_label}
    assert per_label[LABEL_A].precision.status == "computed"
    assert per_label[LABEL_A].precision.value == "2/3"


def test_repeated_computation_is_byte_identical():
    """Same inputs -> identical serialized result, run twice independently."""

    reference = _reference_spans()
    evaluator = _evaluator_spans()
    eligibility = ResearchAnnotationService._validation_eligibility(
        "exhaustive",
        (
            DecisionRevisionRecord(
                decision_uuid="00000000-0000-0000-0000-000000000003",
                prediction_id="span_" + "1" * 40,
                projection_type="span_annotation",
                revision_number=1,
                decision="confirmed",
                reviewer_reference="reviewer_test",
                created_at="2026-01-01T00:00:00+00:00",
            ),
        ),
    )

    def _run() -> str:
        outcomes = match_spans_exact(evaluator, reference)
        metrics = compute_span_classification_metrics(
            outcomes,
            eligibility,
            metric_implementation_version="span-classification-v1",
            matching_policy_identifier="exact_span_match",
            matching_policy_version="1.0",
        )
        return metrics.model_dump_json()

    assert _run() == _run()
