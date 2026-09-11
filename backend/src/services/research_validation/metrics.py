"""The one implemented Item 3A metric family: span/label classification.

@remarks
Scope for this pass is exactly TP/FP/FN, precision, recall, F1 -- per label,
micro-averaged, and macro-averaged -- computed from a matching policy's
`SpanMatchOutcome` tuple (see `matching.py`). Relation metrics, global/ordinal
score metrics, and turn-classification metrics are out of scope and are not
present in this module at all (not stubbed).

`label_accuracy` (listed as a metric identifier the Item 2A eligibility gate
already knows about) is deliberately NOT computed here: eligibility-wise it
would slot into this same family, but computing it meaningfully requires a
second, position-only match key ("did the evaluator localize this span
correctly, regardless of label") to ask "how often was the label right given
correct localization." Overloading the single `exact_span_match` key (which
already requires label equality to count as a match at all) for that purpose
would produce a number that looks like accuracy but isn't -- so it is left
absent from this dispatch rather than faked. A future metric family can add
it once a position-only match key exists.

Every ratio is an exact reduced fraction (`fractions.Fraction`), never a
float, so results are reproducible byte-for-byte: no floating-point rounding,
no dict-ordering-dependent accumulation, and label iteration is always
alphabetically sorted.
"""

from __future__ import annotations

from fractions import Fraction

from domain.models.research_annotation import ValidationEligibilityRecord
from domain.models.research_validation import (
    RatioResult,
    SpanClassificationAggregate,
    SpanClassificationMetrics,
    SpanLabelClassificationMetric,
)
from services.research_validation.matching import SpanMatchOutcome

_METRIC_BY_RATIO = {
    "precision": "span_precision",
    "recall": "span_recall",
    "f1": "span_f1",
}


def _fraction_str(numerator: int, denominator: int) -> str:
    return str(Fraction(numerator, denominator))


def _eligibility_note(eligibility: ValidationEligibilityRecord, metric_identifier: str) -> str:
    record = next(
        item for item in eligibility.metrics if item.metric_identifier == metric_identifier
    )
    return record.explanation


def _ratio_for_label(
    ratio_name: str,
    numerator: int,
    denominator: int,
    *,
    support: int,
    eligibility: ValidationEligibilityRecord,
) -> RatioResult:
    metric_identifier = _METRIC_BY_RATIO[ratio_name]
    eligible = metric_identifier in eligibility.eligible_metric_identifiers
    if not eligible:
        return RatioResult(
            status="ineligible",
            note=_eligibility_note(eligibility, metric_identifier),
        )
    if support == 0:
        return RatioResult(
            status="no_reference_support",
            note="No reference instances for this label under the annotation set's coverage.",
        )
    if denominator == 0:
        return RatioResult(
            status="no_predicted_support",
            note="The evaluator produced no predictions of this label to compute precision from.",
        )
    return RatioResult(status="computed", value=_fraction_str(numerator, denominator))


def _aggregate_ratio(
    ratio_name: str,
    numerator: int,
    denominator: int,
    *,
    eligibility: ValidationEligibilityRecord,
) -> RatioResult:
    metric_identifier = _METRIC_BY_RATIO[ratio_name]
    eligible = metric_identifier in eligibility.eligible_metric_identifiers
    if not eligible:
        return RatioResult(
            status="ineligible",
            note=_eligibility_note(eligibility, metric_identifier),
        )
    if denominator == 0:
        return RatioResult(
            status="no_reference_support" if ratio_name != "precision" else "no_predicted_support",
            note="No instances exist to compute this aggregate from.",
        )
    return RatioResult(status="computed", value=_fraction_str(numerator, denominator))


def _macro_average(
    ratio_name: str,
    per_label_values: tuple[Fraction, ...],
    *,
    eligibility: ValidationEligibilityRecord,
) -> RatioResult:
    metric_identifier = _METRIC_BY_RATIO[ratio_name]
    eligible = metric_identifier in eligibility.eligible_metric_identifiers
    if not eligible:
        return RatioResult(
            status="ineligible",
            note=_eligibility_note(eligibility, metric_identifier),
        )
    if not per_label_values:
        return RatioResult(
            status="no_reference_support",
            note="No labels had a computed value to average.",
        )
    average = sum(per_label_values, Fraction(0)) / len(per_label_values)
    return RatioResult(status="computed", value=str(average))


def compute_span_classification_metrics(
    outcomes: tuple[SpanMatchOutcome, ...],
    eligibility: ValidationEligibilityRecord,
    *,
    metric_implementation_version: str,
    matching_policy_identifier: str,
    matching_policy_version: str,
) -> SpanClassificationMetrics:
    """Compute the full per-label + micro + macro span-classification result."""

    per_label: list[SpanLabelClassificationMetric] = []
    for outcome in sorted(outcomes, key=lambda item: item.label):
        support = outcome.support
        predicted_count = outcome.predicted_count
        if support == 0:
            # Per the explicit zero-reference-instance rule: never a misleading
            # number for this label, even where precision would otherwise be
            # computable from predictions alone.
            precision = _ratio_for_label(
                "precision", 0, 0, support=support, eligibility=eligibility
            )
            recall = _ratio_for_label("recall", 0, 0, support=support, eligibility=eligibility)
            f1 = _ratio_for_label("f1", 0, 0, support=support, eligibility=eligibility)
        else:
            precision = _ratio_for_label(
                "precision",
                outcome.true_positives,
                predicted_count,
                support=support,
                eligibility=eligibility,
            )
            recall = _ratio_for_label(
                "recall",
                outcome.true_positives,
                support,
                support=support,
                eligibility=eligibility,
            )
            f1_denominator = 2 * outcome.true_positives + outcome.false_positives + (
                outcome.false_negatives
            )
            f1 = _ratio_for_label(
                "f1",
                2 * outcome.true_positives,
                f1_denominator,
                support=support,
                eligibility=eligibility,
            )
        per_label.append(
            SpanLabelClassificationMetric(
                label=outcome.label,
                support=support,
                predicted_count=predicted_count,
                true_positives=outcome.true_positives,
                false_positives=outcome.false_positives,
                false_negatives=outcome.false_negatives,
                precision=precision,
                recall=recall,
                f1=f1,
            )
        )

    total_tp = sum(outcome.true_positives for outcome in outcomes)
    total_fp = sum(outcome.false_positives for outcome in outcomes)
    total_fn = sum(outcome.false_negatives for outcome in outcomes)
    micro_precision = _aggregate_ratio(
        "precision", total_tp, total_tp + total_fp, eligibility=eligibility
    )
    micro_recall = _aggregate_ratio(
        "recall", total_tp, total_tp + total_fn, eligibility=eligibility
    )
    micro_f1 = _aggregate_ratio(
        "f1", 2 * total_tp, 2 * total_tp + total_fp + total_fn, eligibility=eligibility
    )
    micro = SpanClassificationAggregate(
        true_positives=total_tp,
        false_positives=total_fp,
        false_negatives=total_fn,
        precision=micro_precision,
        recall=micro_recall,
        f1=micro_f1,
        labels_included=len(per_label),
    )

    macro_precision_values = tuple(
        Fraction(item.precision.value) for item in per_label if item.precision.status == "computed"
    )
    macro_recall_values = tuple(
        Fraction(item.recall.value) for item in per_label if item.recall.status == "computed"
    )
    macro_f1_values = tuple(
        Fraction(item.f1.value) for item in per_label if item.f1.status == "computed"
    )
    macro = SpanClassificationAggregate(
        true_positives=total_tp,
        false_positives=total_fp,
        false_negatives=total_fn,
        precision=_macro_average("precision", macro_precision_values, eligibility=eligibility),
        recall=_macro_average("recall", macro_recall_values, eligibility=eligibility),
        f1=_macro_average("f1", macro_f1_values, eligibility=eligibility),
        labels_included=len(per_label),
    )

    return SpanClassificationMetrics(
        metric_implementation_version=metric_implementation_version,
        matching_policy_identifier=matching_policy_identifier,
        matching_policy_version=matching_policy_version,
        per_label=tuple(per_label),
        micro=micro,
        macro=macro,
    )
