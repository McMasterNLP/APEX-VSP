# ACE-CT-inspired evaluator: architecture and review plan

Status: proposed experimental design for expert review

Implementation target: `ace_ct_inspired` evaluator version `0.1.0-experimental`

Validation status: `experimental_unvalidated`

Default production evaluator: unchanged

## Purpose

This document defines a reviewable, transcript-based evaluator that lets APEX compare an
ACE-CT-inspired communication rubric with its existing evaluators on the same stored
conversation. The implementation is intended to demonstrate framework integration,
provider-independent structured evaluation, provenance, privacy controls, and non-persisting
comparison behavior.

The output is an experimental software artifact for methodological review. It is not a clinical
decision aid and must not be interpreted as validated evidence about a clinician, learner, or
patient encounter.

## Non-goals

- Reproducing, approximating, or claiming equivalence to an official ACE-CT automation model.
- Reproducing training data, model weights, prompts, experiments, or results from unpublished
  work.
- Replacing trained human raters or validating communication competence.
- Evaluating diagnosis, treatment, medical correctness, or any clinical threshold.
- Changing APEX's default evaluator or canonical production score policy.
- Inferring audio, video, timing, identity, or case facts that are absent from the transcript.

## Experimental and unvalidated status

Every framework result must identify itself as `ACE-CT-inspired`, use implementation type
`experimental_transcript_rubric`, set validation status to `experimental_unvalidated`, and set
publication reproduction to `false`. The versioned rubric remains
`pending_expert_review`. Live evaluation is refused unless the caller supplies an explicit
experimental override. Test fakes may exercise the pending rubric without external calls.

The output must never be described as an official ACE-CT score, a clinically validated score,
or a reproduction of another automation system.

## Confidentiality boundary and source provenance

The implementation is informed by an authorized confidential manuscript supplied locally by
its owner/authors. That source is internal and not publicly citable. It may inform narrow design
choices, but repository content must not contain its unpublished prompt, private examples,
dataset details, tables, model results, or verbatim rubric anchors.

Source-provenance note for the proposed dimensions and domain organization:

> authorized confidential manuscript; public citation pending expert confirmation

A public bibliographic record is available for:

> Arora, A. K., et al. (2026). Multi-methods development and validation of a tool for use in
> measuring serious illness communication competence: Assessment of clinical encounters -
> Communication tool (ACE-CT). *Patient Education and Counseling, 144*, 109465.
> https://doi.org/10.1016/j.pec.2025.109465

The article is the only public citation currently recorded here. Its bibliographic availability
does not establish that the complete rubric or exact score anchors are public or authorized for
repository reproduction. Until the framework owner confirms that point, the code will contain
only original, high-level placeholder descriptions and will remain gated.

## Public-source requirement

Framework claims, production rubric wording, and scoring anchors must be traceable to a public
authorized source or to explicit written permission suitable for repository publication. Each
rubric version records a citation, publication status, approval status, and implementation
status. Exact unpublished anchors are not included in code, prompts, tests, examples, or logs.

An expert-approved source update requires a new rubric version. It must not silently alter the
meaning of an existing version.

## Complete data flow

1. A normal plugin run loads the stored session and turns through existing repositories. A
   comparison run receives the same stored turn entities but performs no writes.
2. The transcript projector validates source turns, orders them by `turn_number`, maps APEX
   roles to clinical roles, minimally normalizes text, and emits an immutable transcript plus
   warnings.
3. The projector obtains the source transcript hash from the comparison pipeline's existing
   canonical hash function.
4. The selected versioned rubric is loaded from one source of truth. Approval gating occurs
   before prompt construction or adapter invocation.
5. The prompt builder produces exactly two messages: system instructions and a user payload
   containing rubric metadata, a strict output contract, and the interleaved transcript.
6. The evaluator service calls an injected provider adapter at temperature `0`. It never
   instantiates a provider and never writes database state.
7. The service removes optional JSON fences, parses the response, and applies strict schema,
   rubric, assessability, evidence-turn, and length validation.
8. A deterministic projection computes domain summaries and explicitly labeled APEX
   compatibility fields. Null dimensions are excluded, not imputed.
9. The plugin wrapper returns the existing APEX feedback contract. Persistence is permitted
   only through the normal explicitly selected session-evaluator path.
10. The comparison path reuses the same computation core, sanitizes framework results, and
    writes only a privacy-safe artifact. It does not persist feedback, metrics, session fields,
    or turns.

## Transcript projection

### APEX role mapping

| APEX role | Projected role |
|---|---|
| `user` | `clinician` |
| `assistant` | `patient` |

No other role is accepted. Roles are mapped only; they are never inferred from text.

### Turn ordering and validation

- Input may be an APEX turn entity or an equivalent mapping.
- `turn_number` must be a positive integer. Booleans, floats, numeric strings, zero, and
  negative values are invalid.
- Duplicate turn numbers are rejected before prompt construction.
- Turns are sorted by ascending `turn_number`; source turn numbers are preserved.
- Gaps are permitted because the projector must not invent missing content.
- Unknown or missing roles are rejected.
- Missing or non-string text is rejected. Unicode text is preserved.
- Database identifiers, user identifiers, case metadata, timestamps, and model settings are not
  copied into the projected transcript.

### Empty and malformed turns

After minimal normalization, an empty turn is retained and produces an
`empty_text_retained` warning tied to its source turn number. Retention preserves ordering and
evidence coordinates and avoids inventing a statement. The prompt identifies the turn as empty.
An evaluator may treat the absence of usable evidence as a reason for a null dimension score.

Malformed structure, invalid numbering, duplicate numbers, unknown roles, and non-string text
are errors, not warnings. A wholly empty transcript is structurally representable for hashing
and deterministic testing, but live rubric evaluation should return insufficient evidence
rather than fabricate scores.

### Text normalization

Only these transformations are allowed:

1. Convert CRLF and bare CR line endings to LF.
2. Remove whitespace surrounding the complete turn text.

Internal spacing, internal newlines, spelling, grammar, disfluencies, and Unicode are otherwise
preserved. The projector does not correct, summarize, reorder, merge, split, or infer content.

### Transcript hash

The `transcript_hash` is the SHA-256 value returned by the existing comparison function
`hash_transcript` for the original source turns. This keeps the ACE-CT result directly joinable
to baseline and hybrid results evaluated on the same comparison input. The hash therefore
follows the comparison pipeline's canonical source serialization, including source APEX roles
and source text, rather than defining a second hash over projected roles or normalized text.
Database IDs and identity are absent from that canonical representation.

### Model-input serialization

Each projected turn is serialized on its own labeled block, for example:

```text
[Turn 1 | Clinician] I would like to understand what matters most to you.
[Turn 2 | Patient] I am worried about what happens next.
```

Empty text is serialized with an explicit non-content marker defined by the prompt builder. The
marker is not treated as evidence from either speaker.

### Implemented projection contract

Checkpoint 2 implements this behavior in `schemas.ace_ct` and
`services.ace_ct_transcript`. The typed representation uses frozen Pydantic models and tuples so
callers cannot mutate projected turns or warnings after validation. Empty text is retained as an
empty string in the model and rendered as `[[EMPTY TURN: NO TRANSCRIPT TEXT]]` only during
model-input serialization. The projector rejects non-string and missing text rather than
coercing it, and computes the canonical hash only from validated source fields.

### Why conversational interleaving is preserved

Communication behavior depends on sequence: a clinician response can only be interpreted in
relation to what preceded it, and a question can only be interpreted in relation to the reply
that follows. Grouping all clinician speech separately from all patient speech destroys this
adjacency and can misattribute evidence. The projector therefore preserves turn-level
interleaving after deterministic source-number ordering.

## Proposed rubric specification

### Stable dimension identifiers and domains

| Order | Identifier | Domain | Original high-level description for review |
|---:|---|---|---|
| 1 | `respond_to_emotion` | `respond` | Recognize and respond constructively to expressed emotion. |
| 2 | `elicit_person_perspective` | `listen` | Invite the person's perspective using listening-oriented techniques. |
| 3 | `avoid_interrupting_or_diverting` | `listen` | Preserve the person's conversational lead without unnecessary interruption or redirection. |
| 4 | `assess_understanding` | `listen` | Explore what the person understands about the illness or issue. |
| 5 | `discuss_hopes_priorities_worries_fears` | `listen` | Invite discussion of personally important hopes, priorities, worries, or fears. |
| 6 | `ask_permission_to_progress` | `speak` | Seek permission before moving the conversation forward or changing focus. |
| 7 | `avoid_unexplained_clinical_terminology` | `speak` | Use accessible language and explain necessary clinical terms. |
| 8 | `offer_question_opportunities` | `general` | Make space for the person to ask questions. |
| 9 | `summarize_conversation` | `general` | Summarize and clarify important content. |
| 10 | `review_next_steps` | `general` | Make next steps understandable and, where observable, collaborative. |
| 11 | `manage_conversation_pace` | `general` | Manage conversational pace in a way that supports the person. |

These descriptions are deliberately concise implementation placeholders. They are not official
rubric anchors and are unsuitable for production scoring until expert approval.

### Proposed text-only assessability matrix

| Dimension | Classification | Transcript evidence available | Missing signal or limitation |
|---|---|---|---|
| `respond_to_emotion` | `partially_assessable` | Words acknowledging, exploring, or dismissing stated emotion | Tone, gesture, facial expression, silence duration |
| `elicit_person_perspective` | `text_assessable` | Question form, reflection, invitation, response sequence | Tone and meaningful silence |
| `avoid_interrupting_or_diverting` | `partially_assessable` | Abrupt topic shifts or explicit redirection | Overlap, interruption timing, pauses |
| `assess_understanding` | `text_assessable` | Questions and checks about the person's understanding | Non-verbal signs of confusion or comprehension |
| `discuss_hopes_priorities_worries_fears` | `text_assessable` | Explicit elicitation and discussion of the named concerns | Unspoken affect and visual cues |
| `ask_permission_to_progress` | `text_assessable` | Explicit or indirect permission language near transitions | Prosody and non-verbal assent |
| `avoid_unexplained_clinical_terminology` | `text_assessable` | Terms used, explanations, and verbal understanding checks | Audience-specific prior knowledge unless stated |
| `offer_question_opportunities` | `text_assessable` | Invitations and responses to questions | Non-verbal invitation or discouragement |
| `summarize_conversation` | `text_assessable` | Recap and clarification language | Non-verbal confirmation |
| `review_next_steps` | `text_assessable` | Explicit plan and next-step language | Visual aids or off-record planning |
| `manage_conversation_pace` | `partially_assessable` | Turn distribution, abrupt progression, verbal pacing checks | Timing, pause length, overlap, delivery speed, video |

`text_assessable` does not mean clinically validated; it means the target behavior can in
principle leave direct lexical or sequential evidence in a transcript. `partially_assessable`
requires a limitation note and a conservative confidence. Any dimension may still be null when
the supplied conversation does not contain sufficient opportunity or evidence.

### Missing audio and video signals

The text-only evaluator cannot directly observe prosody, volume, speech rate, interruption
overlap, pause length, silence quality, facial expression, gaze, gesture, posture, use of visual
aids, or non-verbal assent. It also cannot know whether omitted transcript text existed in the
original encounter. These limitations are carried in the rubric, prompt, per-dimension result,
and framework-level result.

### Proposed 1-5 handling

The score type is an integer from 1 through 5. Until approved public anchors are supplied, the
implementation uses explicitly provisional high-level levels:

| Score | Experimental placeholder meaning |
|---:|---|
| 1 | Little or no transcript evidence of the target behavior when an opportunity is observable. |
| 2 | Limited or inconsistent evidence; substantial improvement is apparent from the text. |
| 3 | Mixed or developing evidence with both effective and missed elements. |
| 4 | Strong, consistent transcript evidence with only minor improvement opportunities. |
| 5 | Exceptionally consistent and skillful transcript evidence across relevant opportunities. |

These are original implementation placeholders, not quoted ACE-CT anchors. They must be stored
with `approval_status = "pending_expert_review"`. A score is null when the documented
insufficient-evidence policy applies. Null is not converted to 3 or any other neutral value.

### Implemented rubric contract

Checkpoint 3 implements rubric version `0.1.0-experimental` as the immutable
`ACE_CT_RUBRIC_V0_1` source of truth in `schemas.ace_ct`. It encodes all eleven stable
identifiers, proposed domain assignments, text assessability, modality limits, publication and
source provenance, and five original placeholder levels per dimension. Schema validation
enforces ordering, uniqueness, domain membership, and complete 1-5 anchors. The rubric remains
`pending_expert_review`; `require_ace_ct_rubric_approval` blocks evaluation unless an explicit
experimental override is supplied.

### Insufficient-evidence policy

A dimension score may be null only when at least one of these applies:

- no relevant conversational opportunity or evidence is present;
- the transcript is empty or too incomplete to support the dimension;
- the decisive evidence requires unavailable audio, timing, or video signals; or
- assigning an integer would require inventing context.

The result must still include the dimension, assessability, confidence, concise reasoning,
improvement guidance, and a limitation note. Confidence must remain finite from 0 through 1.

### Implemented evaluation result contract

Checkpoint 4 implements frozen result models for dimensions, domains, score sources, and
limitations. A result must contain all eleven dimensions and all four domain aggregates in
stable order. Domain and assessability values must match the rubric. Scores are strict integers
from 1 through 5 or null under the explicit insufficient-evidence policy; booleans, numeric
strings, decimals, infinities, and NaN are rejected. Evidence coordinates must be positive,
unique, and sorted. Reasoning, recommendations, and limitation notes are bounded. Domain means
and counts are recalculated during validation so a model cannot return inconsistent aggregates.

### Domain aggregation

Each domain score is the arithmetic mean of its non-null dimension scores. The result records
the contributing dimension count and insufficient-evidence count. No weighting or imputation is
applied. A domain with no non-null dimensions has a null score.

The proposed `general` grouping is an implementation convenience for items that are not assigned
to one of the three named skill domains in the internal source. Dr. Lahnala must confirm whether
it should be represented as a formal fourth domain.

## Compatibility mapping to APEX scores

Compatibility scores are projections for the existing comparison schema; they are not
framework-equivalent ACE-CT outputs.

Each non-null rubric score is normalized with:

```text
((score - 1) / 4) * 100
```

| APEX compatibility field | Proposed value | Required source label |
|---|---|---|
| `empathy_score` | Normalized `respond_to_emotion` score | `ace_ct_inspired.dimension.respond_to_emotion` |
| `communication_score` | Mean of normalized non-null ACE-CT-inspired dimensions | `ace_ct_inspired.mean_of_assessable_dimensions` |
| `overall_score` | Mean of normalized non-null ACE-CT-inspired dimensions | `ace_ct_inspired.mean_of_assessable_dimensions` |
| `spikes_completion_score` | Existing APEX baseline SPIKES score | `apex_baseline.spikes_completion_score_not_ace_ct` |

If no dimension is scoreable, the first three fields are null. Nulls are never imputed. The
SPIKES value must never be labeled as ACE-CT-derived. Artifacts must warn that differences in
canonical APEX fields do not establish agreement or disagreement between equivalent frameworks.
If the stable APEX feedback contract cannot represent this mapping honestly, the compatibility
fields remain null while framework-specific results are retained.

## Provider and model provenance

The evaluator service accepts an injected adapter. The comparison/provider resolver may select
`openai`, `gemini`, or a fake test adapter. Every live result records:

- evaluator and plugin identifiers;
- evaluator and rubric versions;
- framework and validation status;
- LLM provider;
- model identifier;
- prompt version;
- rubric approval status; and
- whether the experimental override was used.

The service does not read credentials or instantiate provider clients. Existing baseline runs
must not load model settings. Fake-adapter tests require no credentials. A seeded live run
requires explicit `--allow-live-llm`; no live call is authorized during implementation or
automated testing.

Checkpoint 7 implements an evaluator-only adapter resolver for `openai` and `gemini`, including
safe optional model identifiers and fake-adapter injection that does not load credentials.
Evaluator definitions now declare `requires_llm`, `supported_providers`, and a default provider;
new comparison logic no longer infers requirements from identifier prefixes. Existing hybrid
evaluators remain OpenAI-only. `ace_ct_inspired` supports both providers, is excluded from the
backward-compatible `all` selection, and is rejected by the seeded workflow before settings load
unless `--allow-live-llm` is explicit.

## Implemented prompt contract

Checkpoint 5 implements an original provider-neutral two-message prompt in
`services.ace_ct_prompt`. The system message defines scope, missing modalities, fixed speaker
roles, evidence rules, null handling, output length limits, and the experimental/non-reproduction
boundary. The user message contains safe rubric metadata, each stable dimension identifier once
in an ordered schema section, the provisional generic scale, a strict JSON shape, and the
interleaved transcript. It excludes source provenance, identity, database metadata,
configuration, credentials, raw prompts from other work, and requests for chain-of-thought.

## Privacy behavior

- Projected transcripts contain only source turn number, mapped role, and text.
- Prompts contain no user identity, database ID, case metadata, credentials, or settings.
- Framework evidence stores turn numbers only; transcript quotations are omitted by default.
- Raw prompts and raw model responses are never persisted.
- Complete transcripts and raw model output are never logged.
- Bounded diagnostics use allowlisted categories and lengths and must not include response text,
  transcript text, credentials, or exception representations that could contain those values.
- Comparison JSON is sanitized under the existing explicit transcript opt-in policy.
- Synthetic review examples are labeled `synthetic_fake_model_output` and contain no private
  encounter content.

## Persistence versus comparison behavior

The same computation core serves both paths.

- Normal plugin execution may persist through `ScoringService.generate_feedback` only when the
  ACE-CT-inspired plugin was explicitly frozen onto the session. Existing repository behavior
  remains responsible for persistence.
- The evaluator service and computation core are pure with respect to database writes.
- Comparison runs load data, compute results, and return sanitized artifacts without creating or
  updating feedback, metrics, sessions, cases, users, or turns.
- Failure in one comparison evaluator does not erase or invalidate successful baseline results.
- ACE-CT-inspired output is not added to the default evaluator list selected by `all`; it must be
  explicitly named. A future `all_experimental` alias may be considered separately.

## Failure behavior

- Invalid transcript structure fails before a provider call.
- A pending rubric fails before a live provider call unless experimental override is explicit.
- Adapter exceptions, invalid JSON, excess output, schema violations, rubric mismatches, and
  unknown evidence turns return typed failures.
- The service never substitutes neutral scores, retries with changed semantics, or falls back to
  a different provider silently.
- Plugin failure creates no feedback and overwrites no existing feedback.
- Comparison failure produces an allowlisted error while retaining other evaluator results and a
  valid partial-failure artifact.
- Logs contain category-level diagnostics only.

### Implemented evaluator service contract

Checkpoint 6 implements `ACECTEvaluatorService(llm_adapter)` without a database or provider
constructor. Approval is checked before prompt construction and adapter invocation. The adapter
is called once at temperature zero. Optional plain or JSON markdown fences are removed before a
single JSON parse, after which the strict result and transcript evidence coordinates are
validated. Success and failure are typed. Failures expose only fixed, bounded diagnostics for
approval denial, adapter errors, invalid JSON, invalid schema output, unknown evidence turns, or
excess output. Raw response text, exception text, prompts, transcripts, and credentials are
neither logged nor returned.

## Questions requiring Dr. Lahnala’s review

1. Is the complete ACE-CT rubric public and authorized for implementation?
2. Which public citation should control the rubric?
3. Are the 11 identifiers and four domains correct?
4. Should transcript-only evaluation return a score for partially observable dimensions?
5. Should insufficient evidence produce null or a neutral score?
6. Is the proposed normalized score mapping acceptable?
7. Should ACE-CT output be persisted or comparison-only initially?
8. Does this system-demo work overlap with the anonymous manuscript?
9. May the EACL paper mention the ACE-CT automation work?
10. Which provider/model should be used for the evaluation case study?

Additional disclosure question: what detail about the authorized confidential manuscript may
appear in an EACL submission, public repository, pull request, demo, or review artifact, and who
must approve that disclosure?

## Open methodological questions

- Should `general` be treated as a formal domain or only as an aggregation group?
- Is integer-only scoring faithful to the intended single-rater use, and should averaged human
  ratings be represented differently in later research exports?
- What minimum transcript completeness or opportunity count is required for each dimension?
- Should partially assessable dimensions always be null, or may direct text evidence support a
  conservative score with a limitation?
- Should domain means be reported on the native 1-5 scale, normalized 0-100 scale, or both?
- Are all dimensions equally weighted for any overall communication summary?
- Is `respond_to_emotion` an acceptable compatibility source for APEX empathy, or should that
  field remain null because the constructs are not equivalent?
- Is reusing APEX baseline SPIKES in the plugin output acceptable when it is explicitly labeled
  as external to ACE-CT?
- What rubric versioning and reviewer sign-off process is required before live evaluation?
- Which synthetic scenarios are suitable for inter-rater and model-comparison review?

## Approval checklist

- [ ] Dr. Lahnala confirms the controlling public citation.
- [ ] Framework owner confirms what rubric wording and anchors may be public.
- [ ] Eleven identifiers, stable ordering, and domain assignments are approved.
- [ ] Text-only assessability classifications are approved.
- [ ] Empty-turn and insufficient-evidence behavior are approved.
- [ ] Integer 1-5 handling and any score anchors are approved.
- [ ] Domain aggregation and null exclusion are approved.
- [ ] APEX compatibility mapping and all source labels are approved.
- [ ] Persistence versus comparison-only scope is approved.
- [ ] Provider/model for any future live case study is approved.
- [ ] EACL disclosure and overlap with the confidential manuscript are resolved.
- [ ] Privacy and logging review is complete.
- [ ] Synthetic example is confirmed to contain no confidential or private material.
- [ ] Default production evaluator remains unchanged.
- [ ] No live model call occurs before explicit authorization.
