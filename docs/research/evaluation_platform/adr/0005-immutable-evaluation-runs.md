# ADR 0005: Persist immutable server-generated evaluation runs

- Status: accepted
- Date: 2026-09-01

## Context

Human review needs a durable prediction and transcript coordinate. An Item 1
preview is ephemeral and a client-posted preview cannot prove what the server
executed.

## Decision

Keep preview non-persisting. Add a separate explicit run-and-save action that
executes and validates one evaluator server-side, then transactionally stores
the complete envelope and minimal canonical transcript snapshot in dedicated
research storage. Expose no update operation for either value.

## Consequences

A save after preview may produce a different live/stochastic result and the UI
must say so. Durable research data includes sensitive transcript text and
requires administrator access and deployment retention governance. Production
learner tables remain unchanged.
