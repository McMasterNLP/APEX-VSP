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
| UI is capability-driven and read-only | common result shell and native discriminator switch | renamed-evaluator capability test; no edit-control assertions | Human annotation is Item 2 |
| Exports are structured and sanitized by default | export service and transcript-hash check | JSON/ZIP/redaction/API tests | CSV is normalized, not lossless; hashes remain sensitive |
| ACE-CT-inspired structure is retained | typed native variant and ACE adapter | 11-dimension/four-domain mapping test | Experimental, unvalidated, non-official, not a publication-model reproduction |

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

Cite a tag or immutable commit in the paper, not a moving branch name.

## Captured software verification

The following results were captured on 2026-09-01 from code commit `ed10fff` on
macOS. Test credentials were inert local values and no live/paid provider call
was made.

| Check | Exact scope | Result | Measured time |
| --- | --- | --- | --- |
| Backend regression | `.venv/bin/python -m pytest -q --ignore=tests/services/test_seeded_evaluator_validation.py` with the four documented test environment variables | 644 passed, 5 deprecation warnings | pytest 8.18 s; wall 9.25 s |
| Item 1 backend | five paths in `testing_and_validation.md` | 70 passed, 2 deprecation warnings | pytest 1.71 s; wall 2.34 s |
| Changed backend lint | exact Ruff command in `testing_and_validation.md` | passed, no findings | included directly after focused suite |
| Frontend regression | `npm run test:run` | 103 passed in 11 files | Vitest 4.33 s; wall 5.21 s |
| Item 1 frontend | API, panel, and result-view test paths | 13 passed in 3 files | Vitest 1.97 s; wall 3.32 s |
| Frontend production build | `npm run build` | TypeScript and Vite passed; existing chunk-size warnings | Vite 3.11 s; wall 7.10 s |
| Changed frontend lint | ESLint paths in `testing_and_validation.md` | passed, no findings | run after build |

The backend exclusion is necessary because the legacy
`test_seeded_evaluator_validation.py` module explicitly performs unmocked paid
OpenAI calls and has no pytest marker. All other backend tests ran. The observed
times above are software-verification timings, not evaluator latency benchmarks.

No browser connection was available in the validation environment. Therefore
the manual synthetic-session checklist and screenshots below are **not
captured** and must not be reported as passed. Component/API tests cover the
same states synthetically, but they do not substitute for visual acceptance.

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
  src/api/researchEvaluation.api.test.ts \
  src/components/admin/research/ResearchEvaluationPanel.test.tsx \
  src/components/admin/research/ResearchResultView.test.tsx
npm run build
npx eslint src/components/admin/research \
  src/types/researchEvaluation.ts src/api/research.api.ts \
  src/api/research.api.test.ts src/api/researchEvaluation.api.test.ts
```

## Test evidence to archive

Archive plain-text command output with UTC date, operating system, Python/Node
versions, dependency lock hashes, commit hash, exit status, pass/fail/skip
counts, warnings, and elapsed time for:

1. full backend pytest suite without paid/live calls;
2. focused Item 1 backend suite;
3. backend Ruff checks for changed files;
4. full frontend Vitest suite;
5. focused research component/API suite;
6. frontend production build and ESLint checks;
7. `git diff --check` and clean-worktree confirmation.

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

## Reproducible artifact bundle

An eventual paper bundle should contain only sanitized material: immutable
commit/tag, environment and lock metadata, test logs, synthetic request/result
fixtures, schema documentation, mapping tables, screenshots, timing scripts and
raw timing CSV, and an artifact manifest with SHA-256 checksums. Do not include
credentials, `.env`, real transcripts, raw provider responses, or confidential
manuscript content.
