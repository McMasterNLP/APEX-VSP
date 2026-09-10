# Paper evidence guide

This file is an evidence collection plan, not a results section. Report only
artifacts captured from the named commit and keep sensitive transcripts out of
screenshots and archives.

## Claim-to-evidence matrix

| Candidate claim | Implementation evidence | Validation evidence | Paper caveat |
| --- | --- | --- | --- |
| One versioned envelope preserves native and normalized results | `research_evaluation.py`, APEX/ACE adapters | strict-schema and mapping-completeness tests | Projection does not imply framework equivalence |
| Four explicit evaluator families are available | default adapter registry and descriptor endpoint | registry/API descriptor tests | Three live/experimental paths may be disabled by policy |
| Baseline execution is offline and non-persisting | research orchestration and existing compute-only baseline | service spy tests and manual saved-feedback comparison | Rule-based engineering baseline, not validated AFCE reproduction |
| Live execution is opt-in twice | request schema, server setting, refusal boundary | service/API refusal tests | Provider use also needs governance and credentials |
| One evaluator failure does not erase siblings | per-registration orchestration boundary | synthetic partial-failure service/UI tests | Failure isolation is not result imputation |
| Item 1 preview is capability-driven and read-only | common result shell and native discriminator switch | renamed-evaluator capability test; no preview edit controls | Review requires a separately saved Item 2A run |
| Exports are structured and sanitized by default | export service and transcript-hash check | JSON/ZIP/redaction/API tests | CSV is normalized, not lossless; hashes remain sensitive |
| ACE-CT-inspired structure is retained | typed native variant and ACE adapter | 11-dimension/four-domain mapping test | Experimental, unvalidated, non-official, not a publication-model reproduction |
| Human decisions never rewrite model predictions | immutable envelope/inventory plus append-only decision revisions | entity guards, revision-history, non-mutation, and resolution tests | Reviewed predictions are not a complete gold dataset |
| Review controls follow framework policy and projection capabilities | versioned policy registry and typed correction union | invalid correction, rating/evidence, renamed evaluator, and no-boundary-control tests | Item 2A cannot add false negatives or relations |
| Completion is explicit and recoverable | coverage check, lock, transition history, reasoned reopen | incomplete/lock/write-rejection/reopen/concurrency tests | One administrator/reviewer set; no adjudication |
| Annotation exports preserve auditability while minimizing data | full-review, resolved, and audit profiles | transcript/email/session-ID redaction and explicit transcript opt-in tests | Pseudonymous artifacts remain sensitive |

## Commit evidence

Use `git log --oneline --reverse main..research-evaluation-contract` to capture
the final incremental series. The implementation began with these checkpoints:

| Commit | Evidence boundary |
| --- | --- |
| `8a957e3` | architecture and contract decisions |
| `10cc048` | strict research domain contract |
| `ac36009` | adapter protocol and explicit registry |
| `86d3b8f` | APEX native/projection adapter |
| `b0a7df6` | ACE-CT-inspired native/projection adapter |
| `9cd65bd` | orchestration and export services |
| `b0af045` | admin API boundary |
| `520816a` | admin selection/execution workspace |
| `08dc62c` | capability-driven visualization and accessibility tests |
| `febc393` | complete documentation and deployment notes |
| `ed10fff` | regression-test alignment with the current auth-store boundary |

Item 2A is the following stack on `research-annotation-workspace`:

| Commit | Evidence boundary |
| --- | --- |
| `33fd66c` | annotation architecture and ADRs |
| `4d79e0d` | dedicated persistence schema and reversible migration |
| `bd7f368` | typed correction contract, policies, and capabilities |
| `8eda99b` | immutable server-run-and-save workflow |
| `e3f949c` | append-only decisions, concurrency, completion, and reopen |
| `6c0e28e` | resolved projections and annotation exports |
| `b1373a2` | admin-only annotation API |
| `f862bcc` | saved-run frontend workflow |
| `8135998` | capability-driven review queue and typed controls |
| `c2dd55d` | lifecycle UI, locking/reopening, exports, and privacy hardening |
| `bed3016` | email redaction and resolved-relation completion safeguards |

Cite a tag or immutable commit in the paper, not a moving branch name.

## Captured software verification

The following results were captured on 2026-09-02 from Item 2A implementation
commit `bed3016` on macOS. Test credentials were inert local values and no
live/paid provider call was made.

| Check | Exact scope | Result | Measured time |
| --- | --- | --- | --- |
| Backend regression | `.venv/bin/python -m pytest -q --ignore=tests/services/test_seeded_evaluator_validation.py` with the four documented test environment variables | 675 passed, 5 deprecation warnings | pytest 7.50 s; wall 8.00 s |
| Item 1 backend | five paths in `testing_and_validation.md` | 70 passed, 2 deprecation warnings | pytest 2.10 s; wall 2.60 s |
| Item 2A backend | seven paths in `testing_and_validation.md` | 31 passed, 2 deprecation warnings | pytest 1.73 s; wall 2.16 s |
| PostgreSQL migration SQL | targeted Alembic upgrade and downgrade compilation | both passed; all four tables created/dropped | 127 upgrade lines; 32 downgrade lines |
| PostgreSQL migration round trip | PostgreSQL 16 disposable database initialized with the Item 1 schema and stamped `a1b2c3d4e5f8` | upgrade/downgrade/upgrade passed; table count 4 → 0 → 4; final version `f2a3b4c5d6e7` | 29 check/foreign/unique constraints in the resulting `core` schema |
| Changed backend lint | Ruff over Python files changed from `research-evaluation-contract` | passed, no findings | captured with regression run |
| Frontend regression | `npm run test:run` | 115 passed in 13 files | Vitest 1.98 s; wall 2.64 s |
| Focused research frontend | six API/component paths | 54 passed in 6 files | Vitest 1.59 s; wall 2.27 s |
| Frontend production build | `npm run build` | TypeScript and Vite passed; existing chunk-size warnings | Vite 2.35 s; build-and-lint wall 6.66 s |
| Changed frontend lint | ESLint paths in `testing_and_validation.md` | passed, no findings | captured with focused checks |

The backend exclusion is necessary because the legacy
`test_seeded_evaluator_validation.py` module explicitly performs unmocked paid
OpenAI calls and has no pytest marker. All other backend tests ran. The observed
times above are software-verification timings, not evaluator latency benchmarks.

Component/API tests exercise synthetic data and do not substitute for a
browser connected to a fully configured local backend. Record browser findings
separately below and do not report an unavailable end-to-end step as passed.

### Browser validation status

On 2026-09-02 the local Vite application started successfully at
`http://127.0.0.1:5173`, but the browser-control runtime reported no connected
browser instance. No screenshots or end-to-end visual checks were captured.
The manual checklist below remains pending and must not be represented as
passed; the automated accessible component tests are reported separately.

### Migration validation status

The Item 2A revision was applied, downgraded, and reapplied against PostgreSQL
16 using a production-shaped Item 1 schema. The final database contained the
four dedicated research tables and reported the expected Alembic head. The
named disposable database container was removed after validation.

A separate attempt to replay the repository's entire historical migration
chain into a completely blank database stopped in the pre-existing
`add_unique_open_session_index` revision: earlier legacy revisions create
unqualified tables while that revision expects `core.sessions`. This predates
Item 2A and does not affect the verified `a1b2c3d4e5f8` → `f2a3b4c5d6e7`
round trip, but fresh-database bootstrap should be repaired separately rather
than rewriting published migration history in this branch.

Exact captured commands:

```bash
cd backend
DATABASE_URL='postgresql+psycopg2://u:p@localhost:5432/db' \
SUPABASE_JWT_SECRET='test-secret' OPENAI_API_KEY='test-key' \
GEMINI_API_KEY='test-key' .venv/bin/python -m pytest -q \
  --ignore=tests/services/test_seeded_evaluator_validation.py

DATABASE_URL='postgresql+psycopg2://u:p@localhost:5432/db' \
SUPABASE_JWT_SECRET='test-secret' OPENAI_API_KEY='test-key' \
GEMINI_API_KEY='test-key' .venv/bin/python -m pytest -q \
  tests/migrations/test_research_annotation_migration.py \
  tests/schemas/test_research_annotation.py \
  tests/services/test_research_annotation_policy.py \
  tests/services/test_research_evaluation_run_service.py \
  tests/services/test_research_annotation_service.py \
  tests/services/test_research_annotation_exports.py \
  tests/api/test_research_annotation_api.py

.venv/bin/alembic upgrade a1b2c3d4e5f8:f2a3b4c5d6e7 --sql
.venv/bin/alembic downgrade f2a3b4c5d6e7:a1b2c3d4e5f8 --sql

DATABASE_URL='postgresql+psycopg2://u:p@localhost:5432/db' \
SUPABASE_JWT_SECRET='test-secret' OPENAI_API_KEY='test-key' \
GEMINI_API_KEY='test-key' .venv/bin/python -m pytest -q \
  tests/schemas/test_research_evaluation.py \
  tests/services/test_research_adapter_registry.py \
  tests/services/test_research_adapters.py \
  tests/services/test_research_evaluation_service.py \
  tests/api/test_research_api.py

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

cd ../frontend
npm run test:run
npm run test:run -- \
  src/api/research.api.test.ts \
  src/api/researchEvaluation.api.test.ts \
  src/api/researchAnnotation.api.test.ts \
  src/components/admin/research/ResearchEvaluationPanel.test.tsx \
  src/components/admin/research/ResearchResultView.test.tsx \
  src/components/admin/research/AnnotationSetWorkspace.test.tsx
npm run build
npx eslint src/components/admin/research \
  src/types/researchEvaluation.ts src/api/research.api.ts \
  src/api/research.api.test.ts src/api/researchEvaluation.api.test.ts
```

## Item 2B evidence

Item 2B is the following stack on `research-annotation-workspace`, branch
`research-annotation-authoring`:

| Commit | Evidence boundary |
| --- | --- |
| `fbf2158` | authoring architecture and ADRs |
| `703fca3` | authoring contracts and persistence schema/migration |
| `fc40422` | span/relation/coverage services |
| `2f3f21c` | accessible transcript annotation modes (frontend) |
| `186bffa` | authoring integrity and API test coverage |
| `ef2cda9` | coverage-completeness enforcement fix |

### Captured software verification

Captured 2026-09-02 on macOS from this branch's tip. No live/paid provider
call was made; the `baseline` evaluator used throughout is rule-based and
offline.

| Check | Exact scope | Result |
| --- | --- | --- |
| Backend regression | full `pytest -q` with the four documented test environment variables | 697 passed, 5 deprecation warnings |
| Focused Item 2B backend | the five paths listed in "Focused Item 2B backend tests" (`testing_and_validation.md`) | 34 passed |
| PostgreSQL migration round trip | disposable PostgreSQL 15 database bootstrapped through the full legacy chain (see the Item 2A note on `add_unique_open_session_index`, worked around here by setting `search_path` to include `core` before replay) to `f2a3b4c5d6e7`, then `upgrade c3b4d5e6f7a8` → `downgrade f2a3b4c5d6e7` → re-`upgrade c3b4d5e6f7a8` | passed; three `research_*_revisions` tables created, dropped, and recreated; `RESTRICT` foreign keys confirmed by direct inspection |
| Changed backend lint | Ruff over the Item 2B backend files plus the two files touched while fixing the bugs below | passed, no findings |
| Frontend regression | `npm run test:run` | 126 passed in 14 files |
| Frontend production build | `npm run build` | TypeScript and Vite passed; pre-existing chunk-size warning only |
| TypeScript project check | `npx tsc -b` | passed |
| Changed frontend lint | ESLint over the Item 2B frontend files | passed, no findings |
| `git diff --check` | whole tree | passed, no whitespace errors |

### Browser validation status

Unlike Item 2A, a real Chromium browser (Playwright-driven) was connected to
a locally running backend and frontend for this item, against a disposable
PostgreSQL database and a fully synthetic session fixture. See
[`evidence/item_2b_browser_acceptance/README.md`](evidence/item_2b_browser_acceptance/README.md)
for the exact scenarios exercised, screenshots, and the two defects this pass
found and fixed (a stale adjust-target selection that could silently
misdirect a model-prediction boundary correction onto an unrelated human
annotation, and a relabel/attribute validation deadlock that made it
impossible to ever relabel a human annotation into a label requiring an
attribute the annotation did not already carry). Both fixes carry backend
and/or frontend regression tests. Authentication used a local test-only JWT
and a temporary, reverted, `DEV`-gated bridge — no real or production
Supabase project is configured in this environment, and no such bridge
shipped on this branch.

## Test evidence to archive

Archive plain-text command output with UTC date, operating system, Python/Node
versions, dependency lock hashes, commit hash, exit status, pass/fail/skip
counts, warnings, and elapsed time for:

1. full backend pytest suite without paid/live calls;
2. focused Item 1 and Item 2A backend suites;
3. targeted migration upgrade/downgrade compilation and staging application;
4. backend Ruff checks for changed files;
5. full frontend Vitest suite;
6. focused research component/API suite;
7. frontend production build and ESLint checks;
8. `git diff --check` and clean-worktree confirmation.

Do not copy a count from this guide. Counts change as tests are added; use the
captured output from the cited commit.

## Screenshots to capture

Use a fully synthetic transcript and crop account/browser identifiers.

- existing Session Logs detail with saved feedback plus the non-overwrite notice;
- descriptor list showing baseline offline/default and live evaluators explicit;
- overlapping annotated transcript with written labels and selected detail;
- relation view and evidence-turn focus;
- APEX metrics/findings/limitations with source/comparability text;
- ACE-CT-inspired 11-dimension/four-domain native view and experimental warning;
- partial success with one sanitized failed/refused envelope;
- provenance panel with truncated hash, versions, provider/model, runtime, and
  execution mode;
- export controls and inspected sanitized JSON/ZIP table list;
- saved run, prediction queue, written human/resolved states, and progress;
- typed label/rating/evidence controls with no span-boundary editor;
- Add annotation and Adjust span modes with exact range preview and written
  model/human/correction provenance;
- overlap disambiguation, human revision history, relation composer/list, and
  coverage/eligibility states;
- completed locked set, reopen-reason dialog, and sanitized annotation exports;
- keyboard focus indicator and a narrow-screen layout.

Record screenshot filename, commit, fixture, browser/version, viewport, and the
claim it supports. Screenshots demonstrate interface behavior, not evaluator
validity.

## Runtime measurements

Measure instead of estimating. For each evaluator, record at least 20 runs on a
frozen synthetic transcript after one warm-up, reporting median, interquartile
range, minimum/maximum, failures/refusals, hardware, network condition,
provider/model, commit, and whether runtime is service-reported or wall-clock.
Keep offline baseline and live-provider timing in separate tables.

Also measure validated response bytes and export bytes for representative small
and large synthetic sessions. The implemented service limits are 1,000,000
transcript characters and 5,000,000 validated response bytes; do not present
those limits as observed throughput.

No evaluator-latency benchmark was collected in this implementation run. The
runtime fields are implemented and exercised structurally, but a 20-run study
requires explicit authorization for live-provider cost and a frozen benchmark
environment.

## Statements that must remain qualified

- “AFCE-aligned, rule-based operationalization of selected constructs,” not
  “implements” or “validates AFCE.”
- “ACE-CT-inspired, experimental and unvalidated,” not “ACE-CT automated
  scorer.”
- “Engineering compatibility projection; not framework-equivalent,” not a
  cross-framework score conversion.
- “Passed the cited software tests,” not evidence of construct, clinical, or
  educational validity.
- “Transcript text redacted by default,” not “anonymous” or “de-identified”
  without a separate disclosure-risk assessment.
- “Coverage-gated reference projection,” not “gold performance”; recall and F1
  require exhaustive coverage and adjudication remains future work.

## Reproducible artifact bundle

An eventual paper bundle should contain only sanitized material: immutable
commit/tag, environment and lock metadata, test logs, synthetic request/result
fixtures, schema documentation, mapping tables, screenshots, timing scripts and
raw timing CSV, and an artifact manifest with SHA-256 checksums. Do not include
credentials, `.env`, real transcripts, raw provider responses, or confidential
manuscript content.
