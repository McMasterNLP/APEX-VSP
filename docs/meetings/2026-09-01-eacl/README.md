# September 1, 2026 APEX / EACL Meeting Package

This directory is a self-contained internal briefing for the September 1, 2026 meeting with Dr. Allison Lahnala about APEX and the EACL 2027 Systems Demonstration target.

It depends on the repository state in `ace-ct-inspired-evaluator` and was prepared on `presentation/september-1-eacl-briefing`. It is **not** the production APEX frontend and does not claim that the comparison mockup has been implemented there.

## Package contents

- `apex-eacl-briefing.html` — standalone 15-section presentation and comparison-UI specification.
- `meeting-agenda.md` — timed 45-minute agenda, preparation, outcomes, and guardrails.
- `decision-record.md` — blank decision table and action log for the meeting.
- `presenter-notes.md` — section-by-section talk track, executive/fallback versions, and likely questions.
- `assets/synthetic-transcript.json` — fictional 12-turn difficult-diagnosis transcript with stable evidence numbers.
- `assets/illustrative-comparison.json` — invented evaluator outputs for UI discussion; not observed results.
- `assets/plugin-roadmap.json` — current registry inventory and literature-inspired candidates.

## Open and present locally

No installation or server is required. Open `apex-eacl-briefing.html` directly from Finder, or from this directory run:

```bash
open apex-eacl-briefing.html
```

The presentation makes no fetch, XHR, backend, database, Supabase, OpenAI, Gemini, font, CSS, or JavaScript-library request. The only JavaScript is embedded navigation and comparison interaction.

Presentation controls:

- Use **Previous** and **Next**, the numbered section links, or the left/right arrow keys.
- Use Page Up/Page Down, Home, and End for keyboard navigation.
- In the comparison section, choose an evaluator, then choose an evidence-turn number to highlight the transcript turn.
- If JavaScript is disabled, all sections and all evaluator panels appear in normal document order.
- On a narrow screen, content reflows; dense tables and transcripts remain scrollable.

## Print or export to PDF

1. Open the HTML in current Chrome or Safari on macOS.
2. Choose **File → Print**.
3. Select landscape orientation if the browser does not detect it automatically.
4. Choose **Save as PDF**.
5. Review the preview. Print styles show every section and every evaluator panel, including panels not selected on screen.

The HTML presentation is the source artifact. A generated PDF is not committed by default.

## What is illustrative

- The transcript is wholly synthetic and is not clinical data.
- Every comparison score, strength, improvement, evidence selection, and domain/dimension value in `illustrative-comparison.json` is invented for interface discussion.
- No evaluator or live model produced the mock comparison.
- Runtime is intentionally unavailable.
- Higher mock scores do not imply better accuracy, validity, or learner performance.
- The ACE-CT-inspired four-group/11-dimension direction, placeholder language, partial-observability treatment, null policy, aggregation, naming, and APEX compatibility projection require expert confirmation.
- Literature candidates are proposals inspired by cited public works; they are not implemented systems or reproductions of those papers.

## Confidentiality boundary

An authorized confidential anonymous manuscript informed the experimental ACE-CT-inspired direction. The manuscript itself is not included in this package.

Do not add, copy, move, embed, upload, quote, or reproduce the confidential PDF or any of its private examples, data, exact unpublished language, scoring anchors, trained-model details, performance numbers, or results.

Permitted provenance label:

> authorized confidential manuscript; public citation pending expert confirmation

Public attribution remains separate through the public ACE-CT citation recorded in the repository documentation. This package does not claim that APEX reproduced the manuscript’s model.

## Update the synthetic assets

Keep the three JSON files as the structured source of truth for future revisions:

1. Edit `assets/synthetic-transcript.json` while preserving its explicit synthetic label, stable positive turn numbers, clinician/patient roles, and absence of identity or database fields.
2. Update every evidence reference in `assets/illustrative-comparison.json` so it points to an existing transcript turn.
3. Keep the comparison asset labeled as illustrative and non-empirical unless a separately authorized and sanitized artifact is substituted.
4. Update `assets/plugin-roadmap.json` only after confirming current plugin registration/status in code and distinguishing implementation from proposals.
5. Because the HTML is standalone and performs no file loading, mirror any approved content changes into `apex-eacl-briefing.html`.
6. Re-run JSON, evidence-reference, HTML-target, JavaScript, responsive, and print validation before presenting.

Do not put credentials, environment values, real patient information, database identifiers, private transcripts, raw model responses, or chain-of-thought content in any asset.

## Repository facts represented here

- The non-persisting baseline/hybrid comparison infrastructure is merged into `main`.
- `ACECTInspiredRubricEvaluator` version `0.1.0-experimental` exists only on the ACE feature branch and this descendant presentation branch; it is not merged into `main`.
- The current settings defaults are `DefaultLLMPatientModel`, `ApexHybridEvaluator`, and `ApexMetrics`.
- The ACE evaluator is gated, non-default, unvalidated, explicitly selected, and excluded from the historical `all` evaluator set.
- The current production frontend does not contain the transcript-plus-comparison interface shown in the briefing.

Primary internal source documents are `docs/research/evaluator_comparison.md`, `docs/research/ace_ct_inspired_evaluator_design.md`, `docs/research/ace_ct_review_guide.md`, and `docs/research/examples/ace_ct_comparison_example.json`.

