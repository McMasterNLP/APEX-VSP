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

Item 2A additionally checks server-generated exact envelope/snapshot
persistence, immutable run rows, production-table non-mutation, transcript
mismatch detection, typed policies/corrections, append-only revisions,
optimistic concurrency, lifecycle locking/reopening, and sanitized exports.

Item 2B adds strict canonical selection verification, Unicode conversion,
human-span and relation revision lifecycles, overlap preservation, boundary
correction, policy enforcement, coverage gating, reference projection,
eligibility, privacy-safe expanded exports, and browser interaction evidence.

Focused Item 2B backend tests:

```bash
.venv/bin/python -m pytest -q \
  tests/schemas/test_research_annotation_authoring.py \
  tests/services/test_research_annotation_service.py \
  tests/services/test_research_annotation_exports.py \
  tests/api/test_research_annotation_api.py \
  tests/migrations/test_research_annotation_authoring_migration.py
```

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

Focused Item 2A suite:

```bash
DATABASE_URL='postgresql+psycopg2://u:p@localhost:5432/db' \
SUPABASE_JWT_SECRET='test-secret' \
OPENAI_API_KEY='test-key' \
GEMINI_API_KEY='test-key' \
.venv/bin/python -m pytest -q \
  tests/migrations/test_research_annotation_migration.py \
  tests/schemas/test_research_annotation.py \
  tests/services/test_research_annotation_policy.py \
  tests/services/test_research_evaluation_run_service.py \
  tests/services/test_research_annotation_service.py \
  tests/services/test_research_annotation_exports.py \
  tests/api/test_research_annotation_api.py
```

The migration test exercises table constraints and append-only hooks against
the test database abstraction. PostgreSQL upgrade and downgrade SQL can also be
compiled without connecting to a deployment database:

```bash
.venv/bin/alembic upgrade a1b2c3d4e5f8:f2a3b4c5d6e7 --sql
.venv/bin/alembic downgrade f2a3b4c5d6e7:a1b2c3d4e5f8 --sql
```

Apply the migration against a real PostgreSQL staging database before release;
offline compilation does not verify deployed permissions, locks, or data.
For a target already at Item 1 revision `a1b2c3d4e5f8`, validate the actual
`upgrade f2a3b4c5d6e7`, `downgrade a1b2c3d4e5f8`, and re-upgrade sequence and
inspect the four `core.research_*` tables and constraints. Replaying this
repository's full legacy history into a blank database is a separate bootstrap
concern because a pre-existing revision expects `core.sessions` after earlier
unqualified table creation.

For Item 2B, use a disposable PostgreSQL database at Item 2A revision and run
`upgrade c3b4d5e6f7a8`, `downgrade f2a3b4c5d6e7`, then re-upgrade. Inspect the
three new `core.research_*_revisions` tables, `RESTRICT` foreign keys, unique
object/revision constraints, and indexes. Never point this exercise at a
production or shared database.

Static checks for the changed backend surface:

```bash
.venv/bin/ruff check \
  src/domain/entities/research_annotation.py \
  src/domain/models/research_annotation.py \
  src/domain/models/research_evaluation.py \
  src/repositories/research_annotation_repo.py \
  src/services/research_adapters \
  src/services/research_annotation_export_service.py \
  src/services/research_annotation_policy.py \
  src/services/research_annotation_resolution.py \
  src/services/research_annotation_service.py \
  src/services/research_evaluation_service.py \
  src/services/research_evaluation_run_service.py \
  src/services/research_export_service.py \
  src/controllers/research_controller.py \
  tests/migrations/test_research_annotation_migration.py \
  tests/schemas/test_research_annotation.py \
  tests/schemas/test_research_evaluation.py \
  tests/services/test_research_annotation_policy.py \
  tests/services/test_research_annotation_service.py \
  tests/services/test_research_annotation_exports.py \
  tests/services/test_research_evaluation_run_service.py \
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
- Item 1 preview and run-and-save remain distinct actions;
- saved-run discovery and annotation-set creation use server records;
- capability-driven confirm/reject and typed label/rating/evidence controls;
- no span-boundary or human-add controls in Item 2A;
- written decision/resolution states, progress, queue navigation, and transcript
  mismatch warnings;
- optimistic-conflict refresh, completion readiness, locked controls, required
  reopen reason, and all three sanitized annotation export profiles.
- UTF-16/code-point conversion for emoji and combining marks;
- explicit add/adjust/relation modes, selection composer, Escape cancellation,
  overlap disambiguation, human/model written styling, lifecycle controls, and
  coverage declaration;
- unsupported evaluator state and responsive side-panel composer behavior.

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
10. Use **Run and save for review** once; verify a distinct immutable saved run
    appears and the UI warns that live/stochastic output may differ from preview.
11. Create/open a review set. Confirm, reject, correct one allowed label, and
    for an ACE-CT-inspired fixture correct a rating/evidence set and mark one
    rating insufficient. Verify written states and progress update.
12. Enter Add annotation mode, select one exact synthetic phrase, inspect its
    code-point offsets, assign a permitted label, save, relabel, adjust, retire,
    and restore it. Repeat selection and save using keyboard controls; verify
    Escape clears an unsaved range and restores focus.
13. Correct a model span boundary and confirm its immutable original remains in
    audit history. Create an overlapping span and use disambiguation to inspect
    both. Reject cross-turn and Unicode-surrogate-splitting selections.
14. Create a policy-supported relation, declare prediction-review coverage,
    and inspect eligible/ineligible metric reasons.
15. Attempt completion with unreviewed items, then complete a fully reviewed
    set. Verify decision controls lock. Reopen with a reason and verify history
    remains visible.
16. Download full-review, resolved-projection, and audit-history JSON. Confirm
    default output has no transcript text, email, raw session ID, or credentials
    and includes the reviewed-prediction limitation statement.
17. Reload the session and verify saved learner feedback and production session
    data did not change.

Record the tested commit, browser, session fixture identifier, screenshots,
commands, results, and measured timings in the paper evidence log. Do not report
an unchecked manual step as passed.
