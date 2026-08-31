# Local evaluator comparison

The comparison command runs the baseline, hybrid v1, and hybrid v2 evaluators against one
completed stored session without writing feedback, session metrics, session fields, or turns.
JSON is the canonical output. By default, it contains an anonymized session reference and
turn-linked evidence metadata but no transcript text or user identity.

From `backend/`:

```bash
PYTHONPATH="$(pwd)/src" poetry run python -m scripts.compare_session_evaluators \
  --session-id 123 \
  --evaluators all \
  --output evaluation/session_123_comparison.json
```

Select evaluators with `--evaluators baseline,hybrid_v1`, and use `--overwrite` only when
replacing an existing artifact intentionally. `--include-transcript` explicitly opts into raw
transcript text. Active sessions are rejected unless `--allow-active-session` is supplied.
Add `--csv-summary evaluation/session_123_comparison.csv` for a stable, privacy-safe table with
one compact row per evaluator. JSON remains the canonical artifact; CSV excludes transcript,
feedback, and evidence blobs.

Exit code `0` means every requested evaluator succeeded, `2` means the request was invalid,
and `3` means an artifact was written with one or more evaluator failures. Hybrid evaluators
can make paid model calls in a real run. Automated tests replace those calls with local fakes.

The comparison is descriptive technical evidence. Agreement between evaluators is not clinical
correctness, and no evaluator is identified as superior without external reference labels.

## Four-condition seeded case study

The repository's existing strong, decent, mixed, and weak difficult-diagnosis fixtures can be
run through the baseline evaluator in an ephemeral in-memory SQLite database. From the
repository root, use the canonical offline command:

```bash
make evaluator-case-study-baseline
```

This writes `backend/evaluation/seeded_baseline_case_study.json`. It does not load application
settings, initialize the configured production database, make network calls, or invoke a model.

Hybrid runs are intentionally not a Makefile default. To authorize their paid model calls
explicitly, run this from `backend/`:

```bash
PYTHONPATH="$(pwd)/src" poetry run python -m scripts.run_seeded_evaluator_case_study \
  --evaluators all \
  --allow-live-llm \
  --output evaluation/seeded_evaluator_case_study.json
```

The explicit live-call flag is required because both hybrid evaluators use a paid model adapter.
Automated tests use local fakes and never pass that flag to real adapters. The output contains
sanitized per-condition artifacts and compact paper-table rows, but no raw transcript text.

The existing external panel artifacts are outputs from **LLM judges**, not clinicians or clinical
experts. The seeded study does not automatically compare merged evaluator results to those panel
scores because the measurements are not directly equivalent. This case study is technical
reproducibility evidence, not clinical validation.
