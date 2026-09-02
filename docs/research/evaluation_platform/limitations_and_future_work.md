# Limitations and future work

## Item 1 limitations

- The workspace is administrator-only because the repository has no separate
  researcher authorization model.
- Item 1 previews and exports are computed on demand. Item 2A adds a separate
  explicit server-run-and-save path for durable review records; previews still
  cannot be promoted or posted back as authoritative runs.
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

## Item 2A: human review and annotation

Item 2A implements immutable saved runs, reviewer/guideline-specific annotation
sets, append-only decisions, optimistic concurrency, typed corrections,
completion/locking, audited reopening, resolved projections, and three
sanitized JSON export profiles. It keeps model predictions distinct from human
decisions and never changes learner feedback or production session records.

The current review corpus is intentionally incomplete as a gold standard:

- reviewers can assess model-produced spans, turn labels, relations, ratings,
  and findings only; they cannot add false negatives;
- span boundaries and quoted text cannot be edited;
- relations and findings can be confirmed or rejected but not corrected;
- one reviewer has one set per run/guideline version; independent review,
  blinding, disagreement representation, and adjudication are not implemented;
- the only authorization role is administrator, not a scoped researcher or
  adjudicator role;
- pseudonymization and default text redaction reduce exposure but do not make
  the dataset anonymous;
- no retention/deletion workflow or reviewer assignment queue is provided;
- no validation metric, agreement statistic, model training, or learner-facing
  feedback change is performed.

Item 2B may add new annotations/relations, boundary correction, multiple
reviewers, adjudication, assignments, and governed retention. Each requires a
new policy/contract version rather than reinterpretation of Item 2A records.

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
