# ADR 0008: Store a minimal transcript snapshot and verify integrity

- Status: accepted
- Date: 2026-09-01

## Context

Stable span offsets and evidence references require the exact evaluated text.
The production transcript may later differ or be subject to a separate
lifecycle.

## Decision

Store turn number, semantic/source role, and exact text with the Item 1 hash and
projection version in the immutable run. Exclude identity/profile/auth data and
provider internals. Recompute the current session hash on read and display a
mismatch without altering the snapshot.

## Consequences

Annotation offsets remain durable, but research storage now contains sensitive
text. Deletion/retention is a deployment governance decision; restrictive
foreign keys prevent accidental cascade deletion of provenance.
