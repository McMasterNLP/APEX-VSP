# ACE-CT-inspired evaluator review guide

Audience: Dr. Lahnala and authorized APEX reviewers

Review artifact: `docs/research/examples/ace_ct_comparison_example.json`

## Important status

The example is labeled `synthetic_fake_model_output`. It is generated from a public synthetic
repository fixture with a deterministic fake adapter, contains no transcript text, and is not
experimental evidence. The evaluator is transcript-only, experimental, unvalidated, non-default,
and not an official ACE-CT model reproduction.

The public framework citation currently recorded is Arora et al. (2026), *Patient Education and
Counseling*, 144, 109465, https://doi.org/10.1016/j.pec.2025.109465. Exact anchors in this
implementation are original high-level placeholders. The source-provenance boundary remains:
authorized confidential manuscript; public citation and permissible disclosure pending expert
confirmation.

## What to inspect

### Transcript role mapping and interleaving

Confirm that APEX `user` turns should map to `clinician`, APEX `assistant` turns should map to
`patient`, and ascending source turn numbers should remain interleaved. The example intentionally
omits transcript text; evidence coordinates such as `[2, 3]` demonstrate linkage only.

### Dimension definitions and identifiers

Review all eleven stable identifiers under
`comparison_artifact.observed_results[].framework_results.dimension_results`. Confirm that the
short original descriptions in the versioned rubric are accurate enough for implementation and
do not imply official or approved wording.

### Domain assignment

Confirm the proposed membership:

- `respond`: `respond_to_emotion`
- `listen`: perspective elicitation, avoiding interruption/diversion, assessing understanding,
  and hopes/priorities/worries/fears
- `speak`: permission to progress and accessible terminology
- `general`: question opportunities, summary, next steps, and pace

Also decide whether `general` is a formal fourth domain or only an APEX aggregation group.

### Assessability

Inspect `assessability` and `modality_limitation_notes` on every dimension. In particular, confirm
whether response to emotion, interruption/diversion, and pace should be partially assessable from
text. Decide whether partially observable dimensions may receive conservative scores or must be
null.

### Evidence linkage

Evidence contains turn numbers only. Confirm that evidence should remain unique, sorted, and
limited to turns in the supplied transcript, with no transcript quotation in artifacts by
default. The synthetic example links dimensions to turns 2 and 3 and leaves the pace evidence
empty.

### Score anchors and insufficient evidence

Review the provisional integer 1-5 policy and confirm the controlling authorized public source
before any anchor wording is approved. The example makes `manage_conversation_pace` null because
timing and delivery speed are unavailable. Decide whether this is preferable to a neutral score;
the implementation currently prohibits neutral imputation.

### Domain aggregation

Confirm that each domain should use an unweighted arithmetic mean of non-null member dimensions,
with scored and insufficient-evidence counts reported. A domain with no scored members is null.

### Compatibility mapping

Inspect `scores` and `framework_results.score_sources`. Confirm whether:

- empathy may be projected from normalized `respond_to_emotion`;
- communication and overall may share the normalized mean of non-null dimensions; and
- APEX baseline SPIKES may appear only with the explicit
  `apex_baseline.spikes_completion_score_not_ace_ct` label.

The warning that canonical APEX scores are not framework-equivalent must remain visible.

### Limitations and experimental wording

Confirm the framework label `ACE-CT-inspired`, validation status `experimental_unvalidated`,
publication reproduction `false`, and the missing audio/video/timing/overlap declarations. Review
whether the current language sufficiently prevents clinical-validation or official-model claims.

## Decisions to record

Use the approval checklist and the section **Questions requiring Dr. Lahnala’s review** in
`docs/research/ace_ct_inspired_evaluator_design.md`. In particular, record the authorized public
rubric/citation, dimension/domain approval, null policy, compatibility policy, persistence scope,
provider/model choice, overlap with the authorized confidential work, and what—if anything—may be
disclosed in an EACL paper, public pull request, or demo.
