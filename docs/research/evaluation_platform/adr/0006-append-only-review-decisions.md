# ADR 0006: Store review decisions as append-only revisions

- Status: accepted
- Date: 2026-09-01

## Context

Overwriting a reviewer decision would erase scientific provenance and permit
silent loss across tabs or repeated saves.

## Decision

Store every decision as a new typed revision linked to its original prediction
snapshot and predecessor. Increment an annotation-set revision for every
decision and lifecycle action. Require optimistic expected revisions and
return HTTP 409 on mismatch. Record complete/reopen transitions immutably.

## Consequences

Effective decisions are derived from the latest revisions. Storage grows with
review activity, but audit history is reconstructable and conflicts cannot
silently overwrite newer work.
