# Item 2B browser acceptance record

Captured 2026-09-02 against commit range starting at `fbf2158` (branch
`research-annotation-authoring`), Chromium (Playwright-driven), viewport
1280x900. Backend: FastAPI on a disposable local PostgreSQL 15 container,
migrated to head (`c3b4d5e6f7a8`). Frontend: local Vite dev server. No live
OpenAI/Gemini calls; the `baseline` evaluator is rule-based and offline.

Fixture: one synthetic completed session (case "Item 2B browser acceptance
case") with eight turns covering ASCII, accented characters, curly quotes, an
emoji outside the BMP, a combining-mark comparison, a multiline turn, and a
turn with four repeated occurrences of "worried" — the same Unicode cases
exercised by the backend offset tests. No real learner, patient, or reviewer
data appears anywhere in this fixture.

Authentication used a JWT signed locally with a test-only
`SUPABASE_JWT_SECRET` and a synthetic admin user row (no real or production
Supabase project is configured in this environment); a small, temporary,
`import.meta.env.DEV`-gated bridge was added to `main.tsx`/`authStore.ts` to
inject that session client-side, and was reverted before committing this
branch. It never shipped.

## Scenarios exercised

1. Admin → Session Logs → select the synthetic completed session → Research
   Evaluation panel → saved baseline run → open → create/open annotation set.
2. Add annotation mode: selected "very worried" (turn 2, code points [4,16)),
   composer showed the exact preview/turn/speaker/offsets, saved as a
   human-added `elicitation` span. See `07-selection-composer-open.png`,
   `08-human-annotation-saved.png`.
3. Escape cancelled a pending selection with no write and restored focus to
   the mode toolbar.
4. A selection spanning turn 2 into turn 3 was rejected client-side
   ("Select text within a single transcript turn.") before any request was
   sent. See `10-cross-turn-selection-rejected.png`.
5. Relabeled the human span from `elicitation` to `empathic_opportunity`,
   adjusted its boundaries, retired it, and restored it — each as a new
   append-only revision. See `11-human-annotation-relabeled.png`.
6. Adjust span mode corrected the model-predicted `empathic_opportunity` span
   at turn 2 (`worried` → `very worried`) via a typed decision; the original
   prediction and the resolved/corrected view remained visibly distinct
   (`MODEL PREDICTION`, `Human Decision: Corrected`, `Resolved annotation`).
   See `16-model-span-adjust-composer.png`, `17-model-span-corrected.png`.
7. Overlapping "very"/"worried" segments opened a disambiguation list rather
   than merging or guessing. See `18-overlap-disambiguation.png`.
8. Relation mode created a policy-valid `elicits` relation from the corrected
   `empathic_opportunity` span to a second human-added `elicitation` span
   using stable annotation identities. See `19-relation-mode.png`.
9. Declaring `prediction_review_only` coverage was correctly refused while 16
   of 17 presented predictions remained unreviewed
   (`22-coverage-rejected-incomplete.png`); after reviewing all 17 it
   succeeded, and the returned `validation_eligibility` allowed
   `span_precision`/`label_accuracy` while excluding `span_recall`/
   `span_f1`/`relation_recall`/`relation_f1`/`global_score_agreement` with
   explicit reason codes.
10. Downloaded the sanitized `resolved_projection` export: no raw session ID,
    email, or transcript text; includes transcript hash/provenance and the
    coverage-scoped limitation statement.
11. Keyboard-only pass: Tab reached "Add annotation", Enter activated it,
    native Shift+arrow-style text selection plus the mode's mouseup/keyup
    handlers opened the composer, and Escape returned focus to the mode
    toolbar.

## Defects found and fixed during this pass

Both were caught only by driving the real UI against a real backend, not by
the existing component tests (which mocked the API layer and never exercised
this exact state transition or attribute payload).

- **Stale adjust-target state.** Clicking a human annotation's "Adjust
  boundaries" button left internal state pointing at that annotation even
  after switching to the toolbar's general "Adjust span" mode, so a
  subsequent attempt to correct a *model* prediction's boundary silently
  revised the *human* annotation instead. Fixed in
  `AnnotationSetWorkspace.tsx` (`chooseMode` now always clears the stale
  target) and covered by a new regression test asserting the correction
  lands on the intended prediction.
- **Relabel/attribute deadlock.** Relabeling a human annotation into a label
  that requires an attribute (e.g. `empathic_opportunity` requires
  `explicit_or_implicit`) always failed, and no sequence of `relabel` then
  `edit_attributes` calls could ever succeed: `relabel` validated the new
  label against the annotation's *old* attributes, and `edit_attributes`
  validated any attribute against the annotation's *current* (pre-relabel)
  label. Fixed by letting a `relabel` request also carry replacement
  attributes (`research_annotation_service.py`), with the frontend
  populating a policy default when required
  (`AnnotationSetWorkspace.tsx`), and regression tests on both sides.

## Not re-verified after the fix

Screenshots `01`–`19` and `22` are from the run that found the bugs above (a
still-useful, honest record of an in-progress session); the successful
relation, full-coverage, and export outcomes were re-verified against a fresh
synthetic session after both fixes landed via the same driver script and the
API responses quoted in the final report, but were not re-screenshotted.
