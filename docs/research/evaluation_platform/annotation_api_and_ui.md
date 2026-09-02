# Annotation API and UI

## Authorization

All routes use the existing administrator dependency. Trainees and
unauthenticated callers cannot create, read, review, complete, reopen, or
export research annotation records.

## API sequence

```http
POST /v1/research/sessions/{session_id}/evaluation-runs
GET  /v1/research/sessions/{session_id}/evaluation-runs
GET  /v1/research/evaluation-runs/{run_uuid}

POST /v1/research/evaluation-runs/{run_uuid}/annotation-sets
GET  /v1/research/annotation-sets/{set_uuid}
PUT  /v1/research/annotation-sets/{set_uuid}/decisions/{prediction_id}
POST /v1/research/annotation-sets/{set_uuid}/complete
POST /v1/research/annotation-sets/{set_uuid}/reopen
POST /v1/research/annotation-sets/{set_uuid}/exports
```

Run and save accepts one evaluator identifier, explicit live authorization,
and optional supported provider/model override. It never accepts an envelope.
A successful response returns the stored run UUID, exact validated envelope,
canonical snapshot, current transcript-integrity state, and supported
annotation policy. A failure cannot create an annotation set.

Annotation-set creation requires a guideline identifier/version and optional
bounded set note. The server verifies the run, policy, envelope/adapter
versions, reviewer uniqueness, transcript hash, and non-empty eligible
inventory.

Decision example:

```json
{
  "expected_set_revision": 3,
  "expected_decision_revision": 1,
  "decision": "corrected",
  "correction": {
    "correction_type": "dimension_rating",
    "corrected_score": 4,
    "corrected_score_status": "available",
    "corrected_assessability": "text_assessable",
    "corrected_evidence_turns": [2, 4]
  },
  "reviewer_note": "Turn 4 supplies the clearest evidence."
}
```

Concurrency mismatches return HTTP 409 with current sanitized set and decision
revision numbers. Invalid prediction, policy, correction, lifecycle, or
completion requests return bounded 4xx messages. Provider and adapter failures
never expose raw provider data.

## UI sequence

The existing Admin Session Logs detail contains one research area:

1. **Preview only — not saved** executes Item 1.
2. **Run and save for review** explicitly re-executes and persists a result.
3. Saved runs show immutable provenance and transcript-integrity status.
4. The administrator creates or opens their guideline-specific set.
5. A sequential queue shows model prediction, current human decision,
   correction controls, evidence, note, and progress.
6. Completion validates all required items and locks the set.
7. Reopen uses an explicit reason dialog.
8. Export controls download sanitized full, resolved, or audit JSON.

The UI warns that save reruns the evaluator and a stochastic/live result may
differ from a preview. It labels experimental/unvalidated frameworks and never
describes the resolved output as a complete gold dataset.

## Capability-driven controls

The review card switches on projection type and declared operations. It does
not switch on evaluator identifiers. Span and turn cards expose only allowed
label/dimension choices; relations and findings expose confirm/reject; ratings
expose score, insufficient-evidence, and evidence-turn controls. Span-boundary
fields and human-added annotations have no Item 2A UI.

## Queue and accessibility

The workspace shows item number, total, confirmed/corrected/rejected/
insufficient/unreviewed counts, previous/next controls, and written state
labels. Color is supplementary. Controls have accessible names, visible focus,
and keyboard operation. Selecting an item focuses its transcript/evidence
turns without changing saved offsets.

## Error and recovery states

The UI distinguishes descriptor/run loading, live refusal, failed save, no
reviewable predictions, existing set, decision saving, conflict, invalid
correction, incomplete completion, locked set, failed reopen, transcript
mismatch, export failure, and network failure. On conflict it explains that a
newer revision exists and offers refresh; it does not automatically overwrite.
