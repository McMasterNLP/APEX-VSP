# ADR 0003: Item 1 research runs are non-persisting

- Status: accepted
- Date: 2026-09-01

## Context

Research comparison must not overwrite learner-facing feedback or mutate the
canonical session being evaluated.

## Decision

The research service uses existing computation-only primitives and returns
in-memory envelopes. It never calls feedback persistence, session updates,
turn writes, metrics persistence, or plugin-selection writes. No migration is
created. Access is admin-only under the current authorization system.

## Consequences

Repeated requests create independent ephemeral runs. The client must retain a
result while inspecting or exporting it. Durable review and validation records
are deferred to Items 2 and 3.

## Rejected alternatives

- Reuse session-close persistence: rejected because it overwrites production
  feedback and invokes frozen metrics behavior.
- Add a research-run table now: rejected because persistence semantics,
  reviewer ownership, and retention policy belong to later items.
- Add a researcher role now: rejected because the approved initial scope is
  existing administrators.
