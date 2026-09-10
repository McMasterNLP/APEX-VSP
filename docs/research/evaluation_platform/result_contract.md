# Result contract

## Contract status and authority

`ResearchEvaluationEnvelope.schema_version` is `1.0`. The
`framework_result` is authoritative. `projection` is deterministically derived
by the declared adapter and is not a substitute for native framework meaning.
The API validates both before returning them.

The contract source is
`backend/src/domain/models/research_evaluation.py`; fields not accepted by its
strict Pydantic models are rejected. All models forbid extra fields and are
immutable after validation.

## ResearchEvaluationEnvelope

| Field | Type | Meaning and invariant |
| --- | --- | --- |
| `schema_version` | literal `1.0` | Top-level contract version |
| `run` | `ResearchRunMetadata` | Stable run identity, timestamp, runtime, execution mode, completion/failure status |
| `transcript` | `ResearchTranscriptIdentity` | Canonical SHA-256 identity; never a user/database identity |
| `evaluator` | `ResearchEvaluatorMetadata` | Identifier/version/type and provider/model when applicable |
| `framework` | `ResearchFrameworkMetadata` | Framework/rubric version, validation status, and scientific boundary statement |
| `adapter` | `ResearchAdapterMetadata` | Adapter identifier/version and supported native discriminator |
| `capabilities` | `ResearchCapabilities` | Supported output and future-operation declarations |
| `framework_result` | discriminated native union or null | Required only for success; authoritative |
| `projection` | `ResearchProjection` | Derived typed common representation; empty for failed/refused runs |
| `warnings` | string array | Bounded scientific/execution warnings |
| `status` | `success`, `failed`, or `refused` | Must equal `run.completion_status` |
| `error` | `SanitizedResearchError` or null | Required for failed/refused; absent for success |
| `provenance` | `ResearchProvenance` | Generation time, runtime, live flag, hash algorithms |

Successful envelopes require a native result whose discriminator matches the
adapter's `supported_native_type`. Failed/refused envelopes cannot carry a
native result and never contain a raw exception.

## Transcript identity and returned turns

`ResearchTranscriptIdentity` contains:

- `canonical_transcript_hash`: lowercase 64-character SHA-256 digest;
- `transcript_projection_version`: `apex-canonical-v1`;
- `turn_count`;
- `role_convention`: `user=clinician;assistant=patient`;
- `raw_transcript_included`.

The authorized run response separately returns `ResearchTranscriptTurn`
objects (`turn_number`, normalized clinical role, source APEX role, and text)
for UI annotation. Envelopes themselves mark raw content false. Sanitized
exports omit turns and redact exact span/evidence text by default.

User identity, email, authentication data, database/Supabase identifiers,
credentials, prompts, and chain of thought are not contract fields.

## Run, evaluator, framework, adapter, and provenance

`ResearchRunMetadata` contains a stable `run_id`, ISO timestamp, non-negative
runtime, `offline`/`live`, completion status, and an allowlisted failure
category when not successful. Stable does not mean persisted: the same
transcript, native result, framework/native identifier, and adapter version
produce the same run ID.

Evaluator metadata contains identifier, display name, version, evaluator type,
provider, and exact model identifier where available. Framework metadata
contains identifier, display name, framework version, optional rubric version,
validation status, and the required framework boundary. Adapter metadata
contains identifier/version/native discriminator. Provenance records timing,
the live flag, transcript SHA-256, and SHA-256-truncated-160 object identifiers.

## Framework-native result discriminators

### `apex_feedback` version `1.0`

`ApexFeedbackNativeResult` is the typed research representation of the complete
in-memory `ComputedFeedback` result, excluding only `session_id`, which is an
internal lookup coordinate rather than evaluator output. It contains:

- baseline/hybrid family and the fixed APEX SPIKES/AFCE-aligned identity;
- all four APEX scores;
- EO counts by Feeling/Judgment/Appreciation and explicit/implicit status;
- elicitation and response counts;
- linkage statistics and missed-opportunity counts;
- typed EO, elicitation, and response spans with exact offsets/text;
- typed opportunity-to-elicitation and opportunity-to-response relations;
- missed opportunities;
- SPIKES coverage, timestamps, and strategies;
- question breakdown, bias-probe field, evaluator metadata, and latency;
- strengths, improvement areas, detailed feedback, timeline events, and
  suggested responses.

Span groups enforce the matching native span type. EO spans require dimension
and explicit/implicit status. Elicitation/response spans require subtype. Text
length and offsets must agree, and adaptation checks exact text and clinical
role against the canonical transcript.

The framework statement is exactly: “AFCE-aligned, rule-based operationalization
of selected constructs.”

### `ace_ct_inspired` version `1.0`

`ACECTNativeResearchResult` retains the existing strict
`EvaluatorFrameworkResults` and `ACECTCompatibilityProjection`. Therefore all
eleven dimensions, four proposed domains, native scores/nulls, assessability,
confidence, evidence turns, rationales, recommendations, modality limitations,
assessability counts, score sources, validation/approval state, rubric version,
and compatibility warnings are authoritative and preserved.

The required flags state that it is experimental, non-official, unvalidated,
and not a publication-model reproduction.

### `versioned_extension` version `1.0`

The future extension variant requires a reviewed extension identifier, semantic
schema version, `provider_output_validated=true`, and unique named fields whose
values are bounded JSON primitives or bounded primitive arrays. Nested provider
objects are rejected. Registration and an adapter are still required before an
extension can execute; the variant is not a generic provider-output bypass.

## ResearchProjection

The projection version is `1.0` and contains seven typed collections. IDs are
unique across the projection. Relations must point to existing projected span
IDs.

### SpanAnnotation

`prediction_id`, framework, literal projection type, turn, start/end offsets,
exact quoted text, label, optional dimension/subtype/confidence, source
reference, and optional provenance. Offsets are non-negative and ordered; the
service additionally checks turn existence, end bounds, exact substring match,
and valid role attribution.

### TurnLabel

`prediction_id`, framework, turn, label, optional dimension/subtype/confidence,
optional safe evidence text, source reference, and provenance. Referenced turns
must exist.

### ProjectedRelation

`relation_id`, framework, projected source/target annotation IDs, relation type,
optional confidence, source reference, and provenance. Both endpoints must
exist.

### DimensionRating

`rating_id`, framework, dimension/domain, score, scale min/max, explicit score
status, assessability, confidence, evidence turns, concise rationale, source
reference, and provenance. Available requires an in-range score; insufficient
evidence/not assessable require an explicit null. Evidence turns are positive,
sorted, unique, and present in the transcript.

### GlobalMetric

`metric_id`, name, numeric value and availability, unit/scale, framework,
source label, comparability statement, source reference, and provenance. Value
and availability must agree. ACE compatibility metrics carry: “Engineering
compatibility projection; not framework-equivalent.” A shared numeric scale
never implies theoretical equivalence.

### ResearchFinding

`finding_id`, framework, type (`strength`, `improvement`,
`missed_opportunity`, `warning`, `general_observation`), description, evidence
turns, confidence, source reference, and provenance.

### ResearchLimitation

`limitation_id`, stable code, description, affected outputs, output/framework/run
scope, source label, source reference, and provenance. Current adapters declare
transcript/modality limits, selected-construct or experimental-rubric limits,
and provider variability where applicable.

## Capabilities

Output capabilities are `character_spans`, `turn_labels`, `relations`,
`dimension_ratings`, `global_metrics`, `narrative_findings`, `evidence_turns`,
`framework_native_view`, and `live_execution`.

Future operation declarations are `confirm`, `reject`, `change_label`,
`adjust_span`, `change_rating`, `change_evidence`, `add_annotation`, and
`add_relation`. Every operation is literal false in Item 1. These declarations
do not authorize or expose editing.

## Stable identifiers

Object IDs use a type prefix and the first 160 bits of SHA-256 over canonical
metadata:

```text
transcript hash
+ evaluator identifier
+ framework identifier
+ native identifier
+ digest of the complete native result
+ adapter version
+ projection type
+ stable object location/content coordinate
```

Array position may contribute but is never the sole input. No sensitive
plaintext is concatenated into the exposed ID. A meaningful native result or
adapter-version change deliberately changes derived IDs. Collision probability
at 160 bits is negligible for the expected corpus, but IDs are not authenticity
signatures.

## Source references

Each source reference contains `native_result_type`, safe `native_identifier`,
safe bounded `native_path`, and `adapter_version`. Paths reject identity,
authentication, database, Supabase, token, and email fields. A source reference
locates an authoritative field; it is not a database pointer.

## Adapter mapping coverage

### APEX baseline and hybrid v1/v2

| Native field | Projection destination | Preserved natively | Notes |
| --- | --- | --- | --- |
| Four score fields | `global_metrics[]` | yes | APEX-version comparability statement |
| EO spans | `spans[]` | yes | opportunity label + dimension + explicit/implicit subtype |
| Elicitation spans | `spans[]` | yes | elicitation label + direct/indirect subtype |
| Response spans | `spans[]` | yes | response subtype retained |
| EO→elicitation links | `relations[]` | yes | endpoints remapped to stable projected IDs |
| EO→response links | `relations[]` | yes | endpoints remapped to stable projected IDs |
| Missed opportunities | `findings[]` | yes | evidence turn retained |
| SPIKES timeline / hybrid mapping | `turn_labels[]` | yes | validated mapping preferred when present |
| SPIKES coverage | `global_metrics[]` via SPIKES score | yes | detailed coverage remains native |
| Strengths | `findings[]` | yes | strength |
| Areas for improvement | `findings[]` | yes | improvement |
| Suggested responses | `findings[]` | yes | improvement with evidence turn |
| Detailed feedback | `findings[]` | yes | general observation |
| Count maps, timestamps, strategies, questions, bias probe, latency, evaluator metadata | no generic destination where not semantically uniform | yes | intentionally inspected through native view/export |
| `session_id` | no projection/export | no | prohibited internal lookup coordinate, not evaluator semantics |

The code asserts that every `ComputedFeedback` field appears in the mapping
table; a newly introduced field fails loudly until reviewed.

### ACE-CT-inspired

| Native field | Projection destination | Preserved natively | Notes |
| --- | --- | --- | --- |
| Dimension score/null/scale | `dimension_ratings[]` | yes | all eleven |
| Domain | rating domain + domain `global_metrics[]` | yes | all four proposed groups |
| Assessability/confidence | `dimension_ratings[]` | yes | native semantics retained |
| Evidence turns | ratings/findings | yes | transcript existence validated |
| Rationale | `findings[]` and rating rationale | yes | concise validated model field |
| Improvement recommendation | `findings[]` | yes | one per dimension |
| Domain aggregates | `global_metrics[]` | yes | native-scale 1–5 mean |
| Compatibility scores | `global_metrics[]` | yes | explicitly not framework-equivalent |
| Modality limits | `limitations[]` | yes | audio/video/timing/overlap |
| Validation/publication flags | limitations and framework metadata | yes | experimental/non-official boundary |
| Assessability counts, approval status, score-source map | no additional generic destination | yes | available in native view/export |

The code asserts coverage of every `EvaluatorFrameworkResults` field.

## Error behavior and versioning

Request/session errors are allowlisted and mapped by the controller. Per-run
errors use bounded categories and generic messages. Raw provider exceptions are
logged only as category-level events and are not returned. A failed evaluator
does not remove successful siblings.

Additive optional fields may be introduced under a compatible minor contract
revision. Meaning changes, discriminator changes, removed fields, or invariant
changes require a new schema/native/adapter version as appropriate. Unsupported
native or extension versions fail validation rather than silently dropping
fields.
