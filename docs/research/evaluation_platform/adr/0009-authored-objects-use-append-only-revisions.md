# ADR 0009: Authored objects use stable identities and append-only revisions

- Status: accepted
- Date: 2026-09-02

## Context

Human-added spans and relations must survive relabeling, boundary changes,
retirement, and restoration without losing their prior scientific state.
Model predictions must remain immutable.

## Decision

Store human spans and authored relations in dedicated append-only revision
tables. Each logical object has one stable public identity and monotonically
increasing per-object revisions containing complete resolved state. Correction,
retirement, and restoration append a successor linked with `RESTRICT`; normal
workflow exposes no update or delete route.

Model boundary correction remains a typed Item 2A decision revision referencing
the immutable model prediction. Human relations reference stable model or human
span identities, so endpoint validity is enforced transactionally by the
authoring service.

## Consequences

Active state and audit history are deterministic. Storage grows with reviewer
activity, and relation endpoints cannot be represented by one database foreign
key because they span model inventory and authored objects.

