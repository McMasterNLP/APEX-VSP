# Testing and validation

## Validation layers

Item 1 is checked at six boundaries:

1. strict Pydantic contract and cross-field invariants;
2. adapter registry, deterministic IDs, and source-path safety;
3. APEX and ACE-CT mapping completeness;
4. orchestration, refusal, failure isolation, non-persistence, limits, and
   sanitized exports;
5. admin-only API behavior and transcript-hash verification;
6. capability-driven, accessible frontend rendering and production build.

## Backend commands

From `backend/`, with required test-only environment values supplied:

```bash
DATABASE_URL='postgresql+psycopg2://u:p@localhost:5432/db' \
SUPABASE_JWT_SECRET='test-secret' \
OPENAI_API_KEY='test-key' \
GEMINI_API_KEY='test-key' \
.venv/bin/python -m pytest -q
```

Focused Item 1 suite:

```bash
DATABASE_URL='postgresql+psycopg2://u:p@localhost:5432/db' \
SUPABASE_JWT_SECRET='test-secret' \
OPENAI_API_KEY='test-key' \
GEMINI_API_KEY='test-key' \
.venv/bin/python -m pytest -q \
  tests/schemas/test_research_evaluation.py \
  tests/services/test_research_adapter_registry.py \
  tests/services/test_research_adapters.py \
  tests/services/test_research_evaluation_service.py \
  tests/api/test_research_api.py
```

Static checks for the changed backend surface:

```bash
.venv/bin/ruff check \
  src/domain/models/research_evaluation.py \
  src/services/research_adapters \
  src/services/research_evaluation_service.py \
  src/services/research_export_service.py \
  src/controllers/research_controller.py \
  tests/schemas/test_research_evaluation.py \
  tests/services/test_research_adapter_registry.py \
  tests/services/test_research_adapters.py \
  tests/services/test_research_evaluation_service.py \
  tests/api/test_research_api.py
```

## Frontend commands

From `frontend/`:

```bash
npm run test:run
npm run build
npx eslint src/components/admin/research src/types/researchEvaluation.ts \
  src/api/research.api.ts src/api/researchEvaluation.api.test.ts
```

## Contract and adversarial cases

The schema/service tests cover:

- unknown fields and unknown native discriminators;
- invalid, reversed, mismatched, out-of-range, and out-of-transcript spans;
- invalid evidence turns and broken relation references;
- duplicate and unsafe identifiers/source paths;
- non-finite values and out-of-range confidence/scores;
- missing, null, insufficient-evidence, and not-assessable values;
- success/failure envelope invariants;
- unsupported providers and live execution without both authorizations;
- malformed native/provider output and adapter exceptions;
- transcript/response size limits and transcript-hash mismatches;
- output sanitization and deterministic multi-table ZIP contents;
- one evaluator failing while a successful sibling remains usable;
- no calls to feedback or metrics persistence paths.

## Mapping completeness

APEX tests assert that the mapping table covers every `ComputedFeedback` field,
including the explicit privacy exclusion for operational `session_id`. They
also verify spans, relations, scores, SPIKES data, findings, suggestions, and
hybrid metadata.

ACE-CT tests assert that the mapping table covers every framework-result field,
preserves all 11 dimensions and four domains, and retains assessability,
insufficient evidence, modality limitations, score sources, and compatibility
warnings.

## Frontend acceptance coverage

Component tests verify:

- descriptor loading, offline defaults, incomplete-session blocking, explicit
  live controls, unavailable evaluators, and partial success;
- exact-envelope export calls;
- safe segmented transcript rendering with overlapping annotations;
- malformed spans ignored without HTML injection;
- keyboard-focus evidence navigation;
- relations, grouped ratings, textual metric comparability, findings,
  limitations, provenance, native views, and failed-run states;
- generic section gating by capabilities after changing an evaluator identifier;
- absence of confirm/reject/correction/edit controls.

## Manual synthetic-session checklist

Use a non-sensitive synthetic completed session. Do not use a real patient or
participant transcript.

1. Open **Admin → Session Logs** and select the completed session.
2. Confirm saved transcript, learner feedback, evaluation details, and metrics
   remain visible.
3. Confirm the Research Evaluation notice says it does not overwrite saved
   learner feedback.
4. Load descriptors; baseline is selected, live evaluators are labeled and not
   selected.
5. Run baseline and inspect spans, labels, relations, metrics, findings,
   limitations, native result, provenance, and warnings.
6. Use an evidence-turn action with keyboard and pointer; focus must return to
   the referenced transcript turn.
7. Select a live evaluator while server live execution remains disabled; verify
   a refusal without a provider call.
8. Induce a synthetic evaluator failure in a test environment alongside
   baseline; verify partial success remains visible/exportable.
9. Download full, native, projection, and tabular profiles; inspect JSON schema,
   ZIP table names, redacted text, and common run/provenance keys.
10. Reload the session and verify saved learner feedback and session data did
    not change.

Record the tested commit, browser, session fixture identifier, screenshots,
commands, results, and measured timings in the paper evidence log. Do not report
an unchecked manual step as passed.
