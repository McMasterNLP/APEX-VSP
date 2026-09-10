# ADR 0007: Describe Item 2A output as a reviewed projection

- Status: accepted
- Date: 2026-09-01

## Context

Item 2A can review only predictions that a model produced. It cannot add a
missed span, label, relation, rating, or finding.

## Decision

Call the derived result a reviewed or resolved annotation projection and state
in every resolved export that false negatives are unsupported. Do not call it
a complete gold dataset.

## Consequences

The result supports audited prediction review but cannot establish recall,
complete-reference accuracy, or a gold corpus. Human-added annotations and
adjudication remain future work.
