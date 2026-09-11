"""Explicit typed registration for Item 3A span-matching policies.

@remarks
Mirrors `services/research_adapters/registry.py`: a frozen dataclass
registration keyed by a single string identifier (`policy_identifier`), with
`version` as a nested metadata field rather than compounded into the key.
Registration is explicit and static -- no dynamic discovery.

Adding a second matching policy (e.g. an overlap/IoU policy) means: write a
`match(evaluator_spans, reference_spans) -> tuple[SpanMatchOutcome, ...]`
function with the same shape as `exact_span_match.match_spans_exact`, wrap it
in a `MatchingPolicyRegistration`, and `register()` it under a new
`policy_identifier` below. Metric calculation code (`metrics.py`) is unchanged
by this, since it only ever consumes `SpanMatchOutcome` tuples.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from domain.models.research_evaluation import SpanAnnotation
from services.research_validation.exact_span_match import match_spans_exact
from services.research_validation.matching import SpanMatchOutcome

SpanMatcher = Callable[
    ["tuple[SpanAnnotation, ...]", "tuple[SpanAnnotation, ...]"],
    "tuple[SpanMatchOutcome, ...]",
]


@dataclass(frozen=True)
class MatchingPolicyRegistration:
    """One statically registered span-matching policy and its version metadata."""

    policy_identifier: str
    version: str
    display_name: str
    match: SpanMatcher


class MatchingPolicyRegistry:
    """Ordered explicit registry; dynamic discovery is deliberately unsupported."""

    def __init__(self) -> None:
        self._registrations: dict[str, MatchingPolicyRegistration] = {}

    def register(self, registration: MatchingPolicyRegistration) -> None:
        identifier = registration.policy_identifier
        if identifier in self._registrations:
            raise ValueError(f"Matching policy '{identifier}' is already registered.")
        self._registrations[identifier] = registration

    def get(self, policy_identifier: str) -> MatchingPolicyRegistration:
        try:
            return self._registrations[policy_identifier]
        except KeyError as exc:
            allowed = ", ".join(self._registrations)
            raise ValueError(
                f"Unknown matching policy '{policy_identifier}'. Expected one of: {allowed}."
            ) from exc

    def list(self) -> tuple[MatchingPolicyRegistration, ...]:
        return tuple(self._registrations.values())

    def identifiers(self) -> tuple[str, ...]:
        return tuple(self._registrations)


MATCHING_POLICY_REGISTRY = MatchingPolicyRegistry()
MATCHING_POLICY_REGISTRY.register(
    MatchingPolicyRegistration(
        policy_identifier="exact_span_match",
        version="1.0",
        display_name="Exact span match (turn, offsets, label)",
        match=match_spans_exact,
    )
)
