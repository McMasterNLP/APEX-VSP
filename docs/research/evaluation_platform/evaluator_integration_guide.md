# Evaluator integration guide

## Integration boundary

Item 1 accepts only reviewed evaluators registered in
`build_default_research_adapter_registry`. It does not load an evaluator from a
filename, package name, URL, request body, entry point, or uploaded artifact.
Adding an evaluator is a code-reviewed change with a strict native schema,
deterministic adapter, declared capabilities, tests, and documentation.

A complete integration supplies:

1. a stable evaluator identifier and semantic version;
2. a construct/framework identifier, version, rubric version, validation
   status, and plain-language scientific boundary statement;
3. a strict typed native result whose discriminator is authoritative;
4. an evaluator wrapper that returns a validated native result without
   persisting learner feedback;
5. a deterministic `ResearchResultAdapter` that preserves the native result
   and derives only supported projection primitives;
6. an explicit capability manifest;
7. source references from every projected object to a safe native path;
8. provider/model, privacy, license, timeout, and size-limit documentation;
9. mapping-completeness, malformed-output, failure-isolation, API, UI, and
   export tests.

The native result remains authoritative. Do not force a construct into a
generic field when the meaning does not match. Retain it in a reviewed native
variant, set the generic capability to false, and add an honest limitation.

## Adapter protocol

Adapters implement `ResearchResultAdapter` in
`backend/src/services/research_adapters/base.py`:

```python
class ResearchResultAdapter(Protocol):
    identifier: str
    version: str
    supported_native_types: tuple[str, ...]
    capabilities: ResearchCapabilities

    def build_native_result(self, result, context) -> FrameworkNativeResult: ...
    def project(self, native_result, context) -> ResearchProjection: ...
```

`build_native_result` converts an existing validated computation result into a
typed research-native variant. `project` is a deterministic translation of
that native object and canonical transcript context. It must not call a model,
database, network service, or clock.

## Capability manifest rules

Set an output capability to true only when the adapter can produce that type
with defined semantics. Empty supported output and unsupported output are
different: the UI renders “none produced” for the first and omits the second.

Item 2A declares operations separately for spans, turn labels, relations,
ratings, and findings. An integration may enable only operations covered by a
versioned framework policy and typed correction schema. Span-boundary changes,
new annotations, new relations, and adjudication remain disabled.

## Source references and mapping tables

Every projection object carries:

- native result discriminator and identifier;
- a bounded safe native path;
- adapter version.

Maintain an explicit mapping table beside the adapter and assert in tests that
every native source field is either mapped, retained natively, or deliberately
excluded with a reason. Silent field dropping is a regression.

## Built-in integration examples

### APEX baseline

- Evaluator: `baseline` (`ApexEvaluator` computation path).
- Execution: offline and default-selected.
- Native variant: `apex_feedback`.
- Adapter: `apex.feedback.adapter`.
- Generic outputs: character spans, turn labels, relations, global metrics,
  findings, evidence links, limitations, native view.
- Scientific label: **AFCE-aligned, rule-based operationalization of selected
  constructs.** It is not a full or validated AFCE reproduction.

The APEX mapping covers all `ComputedFeedback` fields. `session_id` is the only
deliberate non-export because it is an operational database identifier; the
research envelope uses a canonical transcript hash instead.

### APEX hybrid v1

- Evaluator: `hybrid_v1`.
- Execution: live, never default-selected.
- Native variant and adapter: shared with APEX because it genuinely returns the
  same validated `ComputedFeedback` structure.
- Preserved distinction: evaluator identifier/version, provider/model,
  execution mode, reviewer phase, and LLM-review metadata.

The request must set `allow_live=true` and the server must set
`RESEARCH_ALLOW_LIVE_EVALUATIONS=true`. Otherwise the service returns a safe
refusal envelope before provider construction.

### APEX hybrid v2

- Evaluator: `hybrid_v2`.
- Execution: live, never default-selected.
- Native variant and adapter: shared APEX contract.
- Preserved distinction: hybrid-v2 evaluator provenance and merge/review
  metadata.

Sharing an adapter does not make v1 and v2 equivalent runs. Evaluator version,
native digest, model provenance, and output determine their identities.

### ACE-CT-inspired

- Evaluator: `ace_ct_inspired`.
- Execution: live and experimental, never default-selected.
- Native variant: `ace_ct_inspired`.
- Adapter: `ace_ct.inspired.adapter`.
- Preserved framework data: all 11 dimensions, four proposed domain
  aggregates, assessability, insufficient-evidence states, evidence turn
  numbers, reasoning, recommendations, confidence, modality limitations, score
  sources, and the separately labeled APEX compatibility projection.

This evaluator must always be described as experimental, unvalidated,
non-official, and not a reproduction of the confidential manuscript's trained
models. Compatibility values are engineering projections and are not
framework-equivalent ACE-CT scores.

## Adding a reviewed future evaluator

1. Define or extend a bounded discriminated native schema. Prefer a dedicated
   variant for a meaningful framework; the `versioned_extension` escape hatch
   accepts only reviewed, versioned, bounded primitive fields.
2. Add the computation-only wrapper. Separate provider response validation from
   research adaptation.
3. Implement a deterministic adapter and field-coverage table.
4. Register one explicit `ResearchAdapterRegistration`; duplicate identifiers,
   inconsistent live declarations, and missing provider declarations fail.
5. Add descriptor and capability rendering tests. Generic frontend sections
   must branch on capabilities, while native rendering branches on
   `native_type`, never evaluator name.
6. Test stable IDs, invalid spans/evidence, unknown fields, non-finite numbers,
   missing/null/insufficient evidence, large results, partial failures,
   sanitization, and authorization.
7. Document validation status, construct limits, license, data transfer, model
   version, retention, and cost.

For annotation authoring, also declare projection-specific operations. A span
policy enumerates labels/dimensions, attributes and values, overlap behavior,
single-turn/contiguous limits, help text, and whether exhaustive annotation is
meaningful. Relation policies enumerate type, source/target labels, and
self-link behavior. Coverage states which claims the task supports. Do not
enable an operation without its matching policy; an unsupported evaluator
remains read-only rather than borrowing APEX labels.

## External services and researcher models

An approved remote service requires an allowlisted integration committed to the
repository, administrator/server authorization, fixed scheme/host policy,
credentials from environment or a secrets manager, timeouts, response byte
limits, strict response validation, sanitized error handling, and documented
data-processing/retention terms. A request-supplied endpoint is prohibited.

Researcher models are integrated through the same reviewed wrapper/adapter
path. Item 1 does not provide arbitrary uploads, arbitrary code execution,
dynamic imports, runtime package installation, or automatic production
registration.
