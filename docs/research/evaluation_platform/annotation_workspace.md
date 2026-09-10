# Human annotation workspace

## Purpose and scope

Item 2A adds administrator-only expert review of model-generated research
predictions. It is additive to Item 1 and to the production learner workflow.
It never rewrites a `ResearchEvaluationEnvelope`, a projected model prediction,
learner feedback, transcript turns, stored metrics, session state, or frozen
plugin selection.

The durable workflow is:

```text
completed session
  -> explicit server-side run and save
  -> immutable research evaluation run
  -> reviewer- and guideline-specific annotation set
  -> append-only decision revisions
  -> derived resolved annotation projection
  -> completion and lock
```

Item 1 preview remains a distinct, non-persisting action. A preview cannot be
posted back and promoted into an authoritative run. Run and save executes the
selected evaluator again on the server, which matters for stochastic or live
evaluators.

## Research uses

The workspace supports inspecting and correcting eligible model predictions,
creating an auditable reviewed-prediction corpus, and exporting provenance for
later analysis. It does not yet support adding false negatives, changing text
boundaries, adding relations, adjudicating reviewers, or measuring evaluator
accuracy.

## Prediction, decision, and resolution

- A **model prediction** is an immutable projected object stored inside the
  authoritative Item 1 envelope.
- A **human decision** is an append-only revision that confirms, rejects, or
  applies a typed correction to one saved prediction.
- A **resolved annotation** is derived at read/export time: confirmed objects
  retain their original value, corrected objects use the validated correction,
  and rejected objects are absent.

Previous decision revisions remain available after another decision supersedes
them. No decision update mutates an earlier row.

## Lifecycle

An annotation set starts in `draft`, moves to `in_review` when its first
decision is saved, and becomes `complete` and locked through one completion
action. Completion requires an effective decision for every prediction in the
eligible inventory captured when the set was created. Informational metrics and
limitations are not review requirements.

A complete set rejects normal decision writes. Reopening is an explicit
administrator action with a bounded reason. It increments the set revision,
adds an immutable transition record, and returns the set to `in_review` without
deleting decisions.

## Review operations

Controls come from projection-type capabilities and the versioned annotation
policy, not evaluator-name conditionals.

| Projection type | Item 2A operations |
| --- | --- |
| Span annotation | confirm, reject, change allowed label/dimension, note |
| Turn label | confirm, reject, change allowed label/dimension, note |
| Relation | confirm, reject, note |
| Dimension rating | confirm, correct score, insufficient evidence, change evidence turns, note |
| Finding | confirm, reject, note |
| Global metric / limitation | informational only |

Item 2B activates explicit Add annotation, Adjust span, and Relation modes when
the policy allows them. Its composer uses exact saved-snapshot selection,
canonical offsets, policy labels/attributes, Save/Cancel, Escape cancellation,
focus restoration, and live announcements. Overlaps remain separate and open
a disambiguation list.

## Framework policy

The APEX SPIKES/AFCE-aligned policy uses the implemented span labels and the
Feeling, Judgment, and Appreciation taxonomy. The ACE-CT-inspired policy uses
the dimensions and ordinal 1-5 scale declared by its versioned native rubric.
The latter remains experimental, unvalidated, non-official, and pending expert
review.

An annotation set records policy, guideline, framework, evaluator, adapter,
rubric, model/provider, transcript, reviewer, and revision provenance. An
incompatible guideline or adapter version is rejected rather than silently
reused.

## Transcript integrity

Each saved run contains only the canonical turn number, semantic/source role,
and exact text required for durable offsets, plus the Item 1 transcript hash
and projection version. It excludes email, profiles, authentication data,
case-owner identity, credentials, prompts, raw provider responses, and hidden
reasoning.

The current session hash is recomputed when a run or annotation set is read.
A mismatch is displayed but never changes the immutable snapshot or moves an
offset to new text.

## Concurrency and recovery

Every decision and lifecycle mutation supplies the expected annotation-set
revision. Updating a prediction that already has a decision also supplies its
expected effective decision revision. A mismatch returns HTTP 409; the client
keeps unsaved form input where practical and offers an explicit refresh.

## Completion, exports, and limitations

Completion locks the set and verifies that all required decisions and resolved
relation endpoints are coherent. Exports provide a full review package, a
resolved projection, and complete audit history. Sanitized export is the
default and pseudonymizes reviewers; transcript text requires a separate
explicit request.

> Item 2B creates coverage-qualified reference projections, not complete or
> adjudicated gold-standard datasets.

Item 2B enables boundary correction, human-added annotations and relations,
and coverage gating. Multiple reviewers and adjudication remain future work.
Future Item 3 may consume frozen reviewed datasets for validation metrics, but Item 2B performs no
precision, recall, F1, accuracy, agreement, or training.
