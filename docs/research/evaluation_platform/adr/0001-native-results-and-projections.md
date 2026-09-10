# ADR 0001: Preserve native results and derive projections

- Status: accepted
- Date: 2026-09-01

## Context

APEX evaluators expose materially different constructs. Flattening them into a
few 0–100 scores would discard evidence, assessability, relations, rubric
semantics, and framework limitations.

## Decision

Each `ResearchEvaluationEnvelope` carries a strictly discriminated,
framework-native result as the authoritative record and a deterministic
normalized projection as a derived convenience layer. Every projected object
contains a source reference back to the native result.

## Consequences

Researchers can inspect and export both representations. Generic UI and
analysis are possible without asserting framework equivalence. Adapters and
mapping-coverage tests become required integration work.

## Rejected alternatives

- Store only generic scores and findings: rejected because it is lossy.
- Store unvalidated provider JSON: rejected because it bypasses schema and
  privacy boundaries.
- Treat compatibility scores as framework-equivalent: rejected because equal
  numeric ranges do not establish construct equivalence.
