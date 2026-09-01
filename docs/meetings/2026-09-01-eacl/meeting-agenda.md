# APEX / EACL 2027 Internal Review Agenda

**Date:** September 1, 2026  
**Duration:** 45 minutes  
**Primary reviewer:** Dr. Allison Lahnala  
**Purpose:** Agree on the scientific, disclosure, validation, and scope decisions needed for a credible EACL 2027 Systems Demonstration submission target.

## Preparation

Before the meeting:

- Open `apex-eacl-briefing.html` locally and confirm previous/next navigation works.
- Review the synthetic transcript and remember that all evaluator values are illustrative, not observed results.
- Keep `decision-record.md` open for live note-taking.
- Do not open, share, quote, or screen-share the confidential manuscript.
- Be ready to show the repository-backed distinction between work merged into `main` and work present only on `ace-ct-inspired-evaluator`.
- If the application or network is unavailable, use the standalone HTML; it requires no backend, database, Supabase, or model provider.

## Timed agenda

| Time | Topic | Focus | Desired concrete outcome |
|---|---|---|---|
| 0–5 | EACL target and desired outcomes | Confirm the September 22 target, current status, and what must be decided today. | Shared definition of a defensible system-demonstration contribution. |
| 5–12 | Current APEX workflow | Case selection, virtual-patient conversation, ordered transcript, evaluation, feedback/metrics, and learner/admin review. | Agreement on the system story that should anchor the paper and demo. |
| 12–20 | Plugin architecture and completed comparison work | Patient model vs evaluator vs metrics; actual registry; non-persisting comparison, hashing, provenance, failure isolation, and exports. | Confirm that evaluator experimentation—not plugin quantity—is the central engineering contribution. |
| 20–28 | ACE-CT-inspired evaluator | Four proposed groups, 11 dimensions, transcript-only assessability, nulls, aggregation, compatibility projection, gating, and confidentiality boundary. | Record scientific and naming corrections; decide what can remain in the EACL scope. |
| 28–35 | Synthetic transcript and comparison walkthrough | Use evaluator tabs and evidence-turn highlighting; discuss what the eventual read-only UI should make inspectable. | Approve or revise the minimal comparison UI specification and evidence presentation. |
| 35–42 | Scientific, disclosure, and validation decisions | Rubric source, partial observability, public claims, first provider/model, validation material, and reviewers. | Resolve as many decision-record rows as possible; explicitly mark unresolved blockers. |
| 42–45 | Owners, dates, and next checkpoint | Confirm immediate work, analysis freeze, review cadence, and submission artifacts. | Named owners, dated next actions, and a confirmed next review date in the decision record. |

## Desired meeting outcomes

By minute 45, aim to have:

1. An approved or corrected framework name and proposed four-group/11-dimension structure.
2. A controlling rubric source or a clear path to written authorization.
3. A policy for partially observable dimensions, null scores, and aggregation.
4. A decision on whether provisional APEX compatibility projections remain visible.
5. An approved confidentiality and public-disclosure boundary.
6. A first provider/model for controlled smoke testing, or explicit criteria for selecting it.
7. A small validation-material plan and a list of expert reviewers.
8. A contribution framing for EACL that does not imply clinical validation or manuscript reproduction.
9. Confirmation that ACE-CT-inspired output remains comparison-only initially unless deliberately changed.
10. Owners, dates, and a next checkpoint.

## Facilitation guardrails

- Treat the official EACL call as authoritative for format and submission mechanics.
- Keep “implemented on `main`,” “implemented on the ACE feature branch,” “illustrative mock,” and “proposed” visibly separate.
- Do not interpret higher illustrative scores as evaluator superiority.
- Do not claim that transcript-only evidence establishes timing, prosody, overlap, or non-verbal behavior.
- Use the provenance label when needed: **authorized confidential manuscript; public citation pending expert confirmation**.

