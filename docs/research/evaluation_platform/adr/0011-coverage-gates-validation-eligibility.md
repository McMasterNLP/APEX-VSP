# ADR 0011: Audited coverage gates validation eligibility

- Status: accepted
- Date: 2026-09-02

## Context

Reviewing presented predictions can support some precision-style analyses but
cannot support recall or F1. A UI label or completed set is insufficient to
establish which completeness claim a reviewer made.

## Decision

Store coverage declarations as append-only reviewer-attributed revisions with
four explicit values. Derive machine-readable metric eligibility from coverage,
policy capabilities, and completed review tasks. Return eligibility and reason
codes only; Item 2B computes no performance metric.

An Item 2A-compatible completion with no prior declaration appends
`fixed_inventory_complete`, never `exhaustive`.

## Consequences

Downstream Item 3 code can refuse unsupported recall, F1, relation, or
gold-standard claims. Reviewers must make an explicit exhaustive declaration
before free-recall metrics can become eligible.

