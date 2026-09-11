"""The one implemented Item 3A matching policy: exact span match.

A predicted span counts a true positive only if ``(turn_number, start_offset,
end_offset, label)`` all exactly equal a reference span. ``dimension`` and
``subtype`` deliberately do NOT participate in the match key (see module
docstring in `registry.py` for why): this is the narrowest defensible
definition of "the evaluator correctly identified and labeled this exact
span," and folding in `dimension`/`subtype` would silently penalize an
evaluator for a secondary attribute disagreement on a span it otherwise
localized and labeled correctly -- a different, stricter question this pass
does not claim to answer.
"""

from __future__ import annotations

from collections import Counter

from domain.models.research_evaluation import SpanAnnotation
from services.research_validation.matching import SpanMatchOutcome

MatchKey = tuple[int, int, int, str]


def _span_key(span: SpanAnnotation) -> MatchKey:
    return (span.turn_number, span.start_offset, span.end_offset, span.label)


def match_spans_exact(
    evaluator_spans: tuple[SpanAnnotation, ...],
    reference_spans: tuple[SpanAnnotation, ...],
) -> tuple[SpanMatchOutcome, ...]:
    """Partition spans into per-label TP/FP/FN counts under exact-match.

    @remarks
    Duplicate identical spans (same key appearing more than once on either
    side) are matched as a multiset via `Counter` intersection -- deterministic
    and independent of input ordering.
    """

    reference_counts: Counter[MatchKey] = Counter(_span_key(span) for span in reference_spans)
    predicted_counts: Counter[MatchKey] = Counter(_span_key(span) for span in evaluator_spans)
    labels = sorted({key[3] for key in reference_counts} | {key[3] for key in predicted_counts})

    outcomes: list[SpanMatchOutcome] = []
    for label in labels:
        label_reference_keys = {key for key in reference_counts if key[3] == label}
        label_predicted_keys = {key for key in predicted_counts if key[3] == label}
        all_keys = label_reference_keys | label_predicted_keys
        true_positives = sum(
            min(reference_counts.get(key, 0), predicted_counts.get(key, 0)) for key in all_keys
        )
        support = sum(reference_counts.get(key, 0) for key in label_reference_keys)
        predicted_count = sum(predicted_counts.get(key, 0) for key in label_predicted_keys)
        outcomes.append(
            SpanMatchOutcome(
                label=label,
                true_positives=true_positives,
                false_positives=predicted_count - true_positives,
                false_negatives=support - true_positives,
            )
        )
    return tuple(outcomes)
