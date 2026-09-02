# Annotation contract

## Persistence boundary

Dedicated research tables store evaluation runs, annotation sets, decision
revisions, and lifecycle transitions. Production `sessions`, `turns`,
`feedback`, and metrics tables are read only during the workflow. Foreign keys
use restrictive deletion behavior so production deletion cannot silently
destroy research provenance.

## Research evaluation run

A run has a random stable UUID distinct from the Item 1 content-derived
`run.run_id`. It records the source session reference, transcript hash and
projection version, minimal canonical transcript snapshot, turn count, complete
validated envelope JSON, evaluator/framework/adapter/rubric/provider/model
provenance, execution mode and time, creator, and status.

Only the server can create a run. It loads a completed session, canonicalizes
the transcript, executes the evaluator, validates the native result and
projection, and stores the exact envelope and snapshot in one transaction.
There is no update endpoint for the envelope or transcript.

## Annotation set

An annotation set identifies one successful run, reviewer, framework, policy,
and guideline version. It stores the transcript hash, immutable eligible
prediction inventory, state, current optimistic revision, optional bounded
note, and lifecycle timestamps.

States are `draft`, `in_review`, and `complete`. `complete` is also the locked
state. The database prevents more than one set for the same reviewer, run,
guideline identifier, and guideline version.

## Eligible inventory

The inventory is captured from the saved envelope when the set is created. It
contains the exact typed prediction snapshot and allowed operation list for
every reviewable span, turn label, relation, dimension rating, or finding.
Metrics and limitations are excluded. A run with no eligible predictions
cannot create an annotation set.

## Decision revisions

Each row contains a UUID, annotation-set reference, prediction ID, typed
prediction/source snapshot, projection type, per-prediction revision number,
decision, typed correction JSON when applicable, bounded note, reviewer,
timestamp, and optional superseded row. The unique key is annotation set,
prediction, and decision revision.

Decision values are:

- `confirmed`;
- `rejected`;
- `corrected`;
- `insufficient_evidence`, a rating-only typed decision.

The last revision for a prediction is its effective decision. Earlier rows are
never updated or deleted.

## Typed corrections

### Span and turn-label correction

The correction carries a complete corrected label and nullable dimension.
Span correction also reserves `corrected_start_char`, `corrected_end_char`, and
`corrected_text`, which must all be null in Item 2A.

### Dimension-rating correction

The correction carries the resolved score/status, assessability, and sorted
unique evidence turns. Available scores must be members of the policy scale.
Insufficient evidence requires a null score and the corresponding status.
Evidence turns must exist in the stored transcript snapshot. Assessability may
change only when the policy declares that operation.

Relations and findings have no correction payload in Item 2A.

## Policies and guidelines

Each supported framework maps to a versioned `AnnotationPolicyDescriptor`:

- policy and policy version;
- guideline identifier/version and validation status;
- review operations per projection type;
- allowed labels/dimensions or rating scale;
- supported envelope schema and adapter versions.

Corrections are rejected when they violate this descriptor. Evaluator names
are not behavior switches.

## Optimistic concurrency

The annotation-set `revision` increments for every saved decision, completion,
and reopen action. A decision request includes `expected_set_revision` and, if
a decision already exists, `expected_decision_revision`. The service compares
both under the transaction lock. A mismatch returns a sanitized conflict and
does not write.

## Completion and transitions

Completion requires one effective, valid decision for every inventory item.
Confirmed relations must retain both resolved endpoint spans. The completion
transaction increments the set revision, marks it complete, records completion
and lock timestamps, and appends a transition event.

Reopen requires a non-empty bounded reason. It increments the revision,
clears the current lock, records `reopened_at`, appends a transition event, and
does not alter decision history.

## Resolved projection

The resolved projection is deterministic:

- confirmed: copy the original prediction unchanged;
- corrected: copy it with the typed resolved fields;
- insufficient evidence: copy the rating with null score and explicit status;
- rejected: omit it.

Every resolved object retains its source prediction identifier/reference.
Human-added objects do not exist in Item 2A. Global metrics and limitations are
not silently treated as reviewed annotations.

## Invariants

- Saved envelopes and transcript snapshots are immutable.
- Client-supplied envelopes are never authoritative.
- Decision rows and transition rows are append-only.
- Reviewers cannot edit complete sets without an audited reopen.
- Prediction, set, transcript, framework, guideline, and reviewer provenance
  must agree on every write.
- Notes and reopen reasons are bounded.
- No endpoint mutates learner feedback or session data.
