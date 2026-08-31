# Local evaluator comparison

The comparison command runs the baseline, hybrid v1, and hybrid v2 evaluators against one
completed stored session without writing feedback, session metrics, session fields, or turns.
JSON is the canonical output. By default, it contains an anonymized session reference and
turn-linked evidence metadata but no transcript text or user identity.

From `backend/`:

```bash
python -m src.scripts.compare_session_evaluators \
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
