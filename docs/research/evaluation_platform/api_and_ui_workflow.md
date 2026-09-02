# API and UI workflow

## Authorization and non-persistence

All Item 1 routes use the existing `require_admin` dependency. There is no new
researcher role. Administrators may evaluate any completed session visible in
the existing Session Logs workflow; trainees and unauthenticated callers are
rejected. Research execution never changes feedback, turns, session state,
metrics, or plugin selections.

## Evaluator descriptors

```http
GET /v1/research/evaluators
Authorization: Bearer <admin token>
```

The response lists the four explicit built-in identifiers (`baseline`,
`hybrid_v1`, `hybrid_v2`, `ace_ct_inspired`) with evaluator/framework/adapter
versions, capabilities, provider requirements, default selection, availability,
and scientific warnings. It does not inspect or import arbitrary packages.

Example excerpt:

```json
{
  "schema_version": "1.0",
  "evaluators": [
    {
      "identifier": "baseline",
      "display_name": "APEX baseline",
      "version": "1.0",
      "requires_live_execution": false,
      "default_selected": true,
      "availability": "available",
      "capabilities": {
        "outputs": {
          "character_spans": true,
          "turn_labels": true,
          "relations": true,
          "dimension_ratings": false,
          "global_metrics": true,
          "narrative_findings": true,
          "evidence_turns": true,
          "framework_native_view": true,
          "live_execution": false
        },
        "annotation_operations": {
          "confirm": true,
          "reject": true,
          "change_label": true,
          "change_dimension": true,
          "adjust_span": false,
          "change_rating": false,
          "mark_insufficient_evidence": false,
          "change_evidence": false,
          "change_assessability": false,
          "add_annotation": false,
          "add_relation": false
        }
      }
    }
  ]
}
```

## Execute evaluations

```http
POST /v1/research/sessions/{session_id}/evaluations
Authorization: Bearer <admin token>
Content-Type: application/json
```

Default/offline request:

```json
{
  "evaluator_identifiers": ["baseline"],
  "allow_live": false
}
```

Explicit live request, accepted only when server policy also enables it:

```json
{
  "evaluator_identifiers": ["hybrid_v1"],
  "allow_live": true,
  "provider": "openai",
  "model_identifier": "approved-model-id"
}
```

The operation is POST because it may execute a model. One to four unique,
registered evaluators may be requested. Provider/model fields are rejected
unless `allow_live=true`. A live evaluator additionally requires
`research_allow_live_evaluations=true`; the ACE-CT-inspired evaluator also
requires its existing experimental-rubric server authorization. Refusal occurs
before provider adapter construction.

The response contains canonical transcript identity, authorized transcript
turns for rendering, and one independent `ResearchEvaluationEnvelope` per
evaluator. A failed/refused evaluator does not hide successful siblings.

Safe request/session statuses are:

| Condition | HTTP behavior |
| --- | --- |
| unauthenticated / trainee | existing 403 authorization response |
| missing session | 404 |
| incomplete session | 409 |
| invalid evaluator/request | 422 |
| validated response exceeds configured size | 413 |
| live execution not authorized | 200 with per-evaluator `refused` envelope |
| evaluator/provider/adapter failure | 200 with sanitized per-evaluator failure when sibling isolation applies |

No prompts, credentials, raw exceptions, or provider response bodies are
returned.

## Export evaluated envelopes

```http
POST /v1/research/sessions/{session_id}/evaluation-exports
Authorization: Bearer <admin token>
Content-Type: application/json
```

```json
{
  "profile": "projection",
  "envelopes": ["<validated envelope object>"],
  "include_transcript_content": false
}
```

Profiles are `full`, `framework_native`, `projection`, and `tabular`. The
endpoint never executes an evaluator. It reloads the canonical session
transcript and rejects an envelope whose transcript hash differs. Item 1 fixes
`include_transcript_content` to false.

The three JSON profiles are authoritative structured documents appropriate to
their scope. Tabular returns `application/zip` with `runs.csv` and populated
projection tables: `spans.csv`, `turn_labels.csv`, `relations.csv`,
`ratings.csv`, `metrics.csv`, `findings.csv`, and `limitations.csv`. JSON—not a
flat CSV—is the lossless representation. Raw transcript and exact span/evidence
text are redacted from exports by default.

## Administrator UI sequence

Within **Admin → Session Logs → selected completed session**:

1. The existing transcript, feedback, evaluation details, and metrics timeline
   remain visible.
2. The Research Evaluation area loads descriptors.
3. Baseline is selected by default; live evaluators show provider requirements
   and remain unselected.
4. The administrator explicitly executes the selection.
5. A common result shell renders provenance, warnings, and only those generic
   sections declared by capabilities and present in the result.
6. Evidence actions focus the referenced transcript turn.
7. Export controls POST the already returned envelopes to the export endpoint.

The workspace displays: **“Research evaluation — does not overwrite saved
learner feedback.”** It has no confirmation, rejection, correction, span
editing, rating editing, or annotation controls.

## Capability-driven rendering

| Capability | Generic UI behavior |
| --- | --- |
| `character_spans` | segmented, safe React span highlighting |
| `turn_labels` | turn label badges |
| `relations` | relation list using projected endpoints |
| `dimension_ratings` | scale/status/assessability panel |
| `global_metrics` | textual metric cards with comparability statements |
| `narrative_findings` | typed findings sections |
| `evidence_turns` | keyboard-accessible evidence focus |
| `framework_native_view` | structured native view and native export |

Framework-specific native layouts use the `native_type` discriminator only.
Evaluator identifiers never determine whether a generic output section is
available.

## Empty, loading, and failure behavior

The UI distinguishes no selection, running, unsupported/empty outputs, live
refusal, evaluator failure, invalid projection, incomplete session, network
failure, and partial success. The execute button and export controls communicate
busy state. Empty supported output says no annotations/results were produced;
an unsupported output section is omitted. Successful results remain usable when
another evaluator fails.
