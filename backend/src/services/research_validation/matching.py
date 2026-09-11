"""Span match outcome shape shared by every matching policy.

@remarks
A matching policy's only job is to partition (evaluator spans, reference
spans) into per-label true/false positive/negative counts. Metric-family
calculators (see `metrics.py`) consume this shape and never need to know how
the partition was decided, so a second matching policy (e.g. an IoU/overlap
policy) can be added later without touching metric code.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpanMatchOutcome:
    """One label's match partition against the exact set of spans considered.

    @remarks
    ``support`` is the reference-span count for this label (equivalently
    ``true_positives + false_negatives``); ``predicted_count`` is the
    evaluator-span count for this label (equivalently
    ``true_positives + false_positives``).
    """

    label: str
    true_positives: int
    false_positives: int
    false_negatives: int

    @property
    def support(self) -> int:
        return self.true_positives + self.false_negatives

    @property
    def predicted_count(self) -> int:
        return self.true_positives + self.false_positives
