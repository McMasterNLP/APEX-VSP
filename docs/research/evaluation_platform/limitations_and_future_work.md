# Limitations and future work

## Item 1 limitations

- The workspace is administrator-only because the repository has no separate
  researcher authorization model.
- Research runs and exports are computed on demand and are not persisted as
  durable research records.
- The baseline is an engineering, rule-based operationalization. It is not a
  validated reproduction of AFCE.
- Hybrid and ACE-CT-inspired execution depends on approved external model
  services and can drift, fail, incur cost, or be non-reproducible.
- The ACE-CT-inspired rubric is experimental, unvalidated, non-official, and is
  not a reproduction of the confidential manuscript's trained models.
- Transcript-only data omits audio, video, timing, interruption, and overlap;
  some communication dimensions are partially or not assessable.
- A normalized projection improves common tooling but does not make different
  constructs, scales, or frameworks equivalent.
- Stable content identifiers support joins and traceability, not anonymity or
  proof of correctness.
- Exports redact direct transcript strings by default, but narrative results and
  hashes still require sensitive-data controls.
- The current UI shows structured native JSON rather than bespoke interactive
  native visualizations for every framework field.
- Response limits are process constants; future deployments may need explicitly
  governed configurable limits and streaming/artifact storage.
- No arbitrary evaluator/model upload or remote endpoint registration is
  supported.

## Item 2: human review and annotation

Item 2 should introduce durable, append-only research review concepts rather
than mutating evaluator predictions:

- annotation/review set and revision schemas;
- confirmation, rejection, corrected labels, adjusted spans, changed ratings,
  changed evidence, new annotations, and relations;
- reviewer pseudonyms/roles, timestamps, provenance, and rationale;
- optimistic concurrency, immutable history, and audit export;
- independent/blinded review, disagreement representation, and adjudication;
- privacy retention rules and access controls distinct from learner feedback;
- accessible UI controls and review-state recovery.

Until these models exist, all annotation-operation capabilities remain literal
false and the Item 1 workspace must remain read-only.

## Item 3: validation runs and analytics

Item 3 should build validation artifacts on top of versioned Item 1 predictions
and Item 2 human references:

- frozen validation datasets and inclusion/exclusion criteria;
- dataset, split, evaluator, rubric, model, adapter, and prompt versioning;
- span precision/recall/F1 with documented matching rules;
- classification metrics, ordinal agreement, calibration, and uncertainty;
- inter-rater agreement and adjudication analyses;
- subgroup/fairness analyses with adequate sample-size and privacy controls;
- confidence intervals, missingness reporting, and predefined statistical plans;
- validation dashboards and reproducible machine-readable reports;
- prospective/external validation before educational or clinical claims.

Compatibility projections must be analyzed separately from native framework
results and must never be relabeled as framework-equivalent.

## Integration roadmap

Before allowing researcher-provided models, define a governance and sandboxing
model: reviewed packaging, signed artifacts, resource/network isolation,
allowlisted egress, secrets separation, licensing, vulnerability scanning,
timeouts/quotas, output schemas, data-processing agreements, and rollback. Item
1 deliberately provides a code-reviewed built-in path instead of implementing
this prematurely.

