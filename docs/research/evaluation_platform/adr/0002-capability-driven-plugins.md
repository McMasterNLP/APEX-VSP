# ADR 0002: Capability-driven plugin behavior

- Status: accepted
- Date: 2026-09-01

## Context

Evaluator-name conditionals couple generic research UI behavior to today's
plugin list and make new evaluator types fragile.

## Decision

Every research evaluator descriptor and envelope declares typed output and
future annotation-operation capabilities. Generic UI sections and export
tables use the manifest plus actual content. Framework-specific native views
may switch on the native-result discriminator.

## Consequences

New evaluator families can reuse the common shell and must accurately declare
capabilities. Item 1 declares annotation-operation compatibility but all edit
operations remain false and no editing controls are exposed.

## Rejected alternatives

- Branch on evaluator identifiers: rejected as non-extensible.
- Infer capabilities only from non-empty arrays: rejected because empty output
  and unsupported output have different meanings.
- Enable future controls from declarations alone: rejected because Item 1 is
  read-only and has no annotation persistence model.
