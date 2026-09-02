# Item 2B researcher integration and evidence guide

## Integrating a reference workflow

Start from a successful saved evaluation run. Create one annotation set using
the run's returned guideline identifier/version; do not invent a policy in the
client. Read `annotation_policy` to decide whether to render span, relation,
attribute, and exhaustive-coverage controls.

Every write uses optimistic concurrency. Send the current annotation-set
revision and, for an existing human object, its current object revision. On
HTTP 409, fetch the set again and let the reviewer reconcile it. Do not retry a
write blindly.

Selections must come from `transcript_snapshot`, not the current learner
session or decorated DOM text. Convert browser UTF-16 positions to Unicode code
points and send the exact half-open substring, hash, turn, and speaker. Treat a
422 integrity failure as stale/invalid input and require reselection.

The returned `reference_projection` is the active derived view. Use revision
arrays for audit, `coverage_level` for the reviewer's bounded completeness
claim, and `validation_eligibility.metrics` for downstream gating. Never infer
recall/F1 eligibility from the number of annotations.

## Persistence and rollback

Migration `c3b4d5e6f7a8` adds:

- `core.research_human_annotation_revisions`;
- `core.research_authored_relation_revisions`;
- `core.research_coverage_declaration_revisions`.

Rows are full immutable snapshots. Annotation-set, reviewer, and superseded-row
foreign keys use `RESTRICT`; endpoint validity spans model and human identities
and is enforced transactionally by the service. Unique constraints prevent
duplicate object revision numbers. Normal APIs expose retire/restore, not hard
delete.

Validate on a disposable PostgreSQL database prepared at `f2a3b4c5d6e7`:

```bash
alembic upgrade c3b4d5e6f7a8
alembic downgrade f2a3b4c5d6e7
alembic upgrade c3b4d5e6f7a8
```

Downgrade removes the three Item 2B tables and therefore must never be used as
a routine data-erasure mechanism.

## Reproducible research artifact

Archive the commit, dependency locks, migration head, annotation contract,
policy/guideline identifiers and versions, immutable run UUID and Item 1 run
ID, transcript hash/projection version, sanitized audit export, test logs, and
browser acceptance record. Raw or privileged transcript exports belong only in
approved research storage.

Software tests can support claims that offsets are converted and verified,
source output remains immutable, human actions are append-only, operations are
policy-gated, derived views are stable, and default exports redact direct text
and identity fields. They do not establish guideline validity, expert
usability, accessibility with every assistive technology, inter-rater
reliability, construct or clinical validity, or model accuracy. Those require
real-user/expert studies and Item 3 analyses.

## Item boundaries

Item 2A supplied immutable saved runs, fixed prediction review, typed decisions,
locking/reopening, and sanitized exports. Item 2B adds exact authoring,
boundary correction, human spans/relations, coverage, reference projection,
and eligibility. Item 3 remains responsible for frozen datasets, matching
rules, metrics, uncertainty, agreement, subgroup analysis, and reporting.
