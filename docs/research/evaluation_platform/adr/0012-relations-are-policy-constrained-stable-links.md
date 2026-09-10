# ADR 0012: Authored relations are policy-constrained stable links

- Status: accepted
- Date: 2026-09-02

## Context

Relations may connect immutable model spans or human-added spans. Raw offsets
do not survive boundary corrections, and an unrestricted graph would permit
invalid types, directions, duplicates, or retired endpoints.

## Decision

Relations reference stable annotation identities. Versioned policy declares
allowed types, source and target labels, self-relation behavior, and whether
relation authoring or exhaustive relation coverage is meaningful. Creation,
correction, retirement, and restoration append revisions. Duplicate active
source/type/target triples are rejected deterministically.

## Consequences

Boundary changes do not break links. Retired endpoints exclude a relation from
the active reference without deleting its audit history. Visual transcript
graphs are optional; an accessible relation list is authoritative for Item 2B.

