# APEX / EACL 2027 Presenter Notes

**Meeting:** September 1, 2026 internal review with Dr. Allison Lahnala  
**Presentation:** `apex-eacl-briefing.html`  
**Primary goal:** Leave with the scientific, disclosure, validation, and scope decisions needed for a credible September 22 submission target.

## Two-minute executive version

APEX is a virtual-patient communication training system: a learner chooses a case, talks with a simulated patient, and receives SPIKES/AFCE-oriented feedback and metrics. The engineering contribution now extends beyond one scoring path. A non-persisting comparison pipeline—already merged into `main`—can run baseline, hybrid v1, and hybrid v2 against the same completed transcript while preserving transcript identity, provenance, runtime, failure isolation, and privacy-safe exports.

On the ACE feature branch, we added a gated, provider-independent, transcript-only ACE-CT-inspired evaluator. It carries four proposed groups and 11 proposed dimensions, structured evidence, assessability limits, and explicitly provisional compatibility fields. It is experimental, unvalidated, not the default, not merged, and not a reproduction of the authorized confidential manuscript. The manuscript informed a high-level framework direction; no private data, models, weights, examples, results, or unpublished anchors were reproduced.

For EACL, the recommended story is the comparison platform: virtual-patient conversation plus inspectable evaluator experimentation. Before September 22, we should restore and verify the full application, settle the rubric/disclosure decisions, run minimal authorized provider smoke tests, build the read-only comparison UI, validate on a small expert-reviewed set, then freeze provenance and produce the paper/demo package. We should not add several large plugins. Today’s decisions are framework wording, observability/null/aggregation policy, compatibility projection, public boundary, provider/model, validation material, contribution framing, persistence scope, owners, and dates.

## Ten-minute fallback walkthrough

Use sections 1, 2, 5, 7, 8, 10, 11, 13, 14, and 15.

1. **Opening (45 seconds):** State the target and emphasize that comparison engineering is complete but scientific review, live validation, UI integration, and submission preparation remain.
2. **What APEX does (45 seconds):** Trace case → conversation → transcript → evaluation → feedback/metrics → review. Name trainee and administrator views.
3. **Plugin architecture (60 seconds):** Patient model generates behavior; evaluator interprets the completed session; metrics plugin measures observable behavior. Selections resolve through the registry and freeze on the session.
4. **Comparison infrastructure (60 seconds):** One transcript, independent evaluator runs, deterministic hash, provenance/runtime, isolated failures, JSON/CSV, no overwrite of learner records.
5. **Mock comparison (90 seconds):** Select ACE-CT-inspired, point to all 11 dimensions and the null pace dimension, then click turns 3 and 5 to show miss/repair evidence. Repeat that all values are illustrative.
6. **Manuscript boundary (60 seconds):** Contrast research benchmarking with APEX integration. Read the boundary sentence; do not discuss unpublished detail.
7. **Engineering status (60 seconds):** Show the clean main/feature split. State that the comparison UI is not yet in production.
8. **Recommended scope (60 seconds):** Prioritize app restoration, decisions, minimal live tests, read-only UI, small validation set, analysis freeze, and submission package. Reject plugin sprawl.
9. **Timeline (45 seconds):** Decisions now, integrated demo next, freeze by September 12, paper/media after freeze, final review September 19–22.
10. **Decisions (75 seconds):** Move directly into the decision record and assign owners/dates.

## Section notes

### 1. Opening — target, status, and today’s outcome

**Main message:** We have a credible engineering base, but a submission-quality scientific claim still depends on decisions and validation.

**Suggested explanation (45–60 seconds):** “The target is EACL 2027 System Demonstrations, with a September 22 submission deadline. The non-persisting evaluator-comparison infrastructure is complete and merged. The ACE-CT-inspired evaluator exists experimentally on its feature branch. What remains is scientific review, controlled live testing, the actual comparison UI, a small validation exercise, and the paper/demo package. Today is about narrowing the claims and unblocking that work.”

**Important caveat:** This is a target, not an acceptance, completed submission, or clinically validated evaluator.

**Question to ask:** “Does evaluator experimentation around a virtual-patient conversation feel like the right primary contribution?”

**Transition:** “To judge that framing, let’s first anchor on what APEX already does.”

### 2. What APEX does — current workflow

**Main message:** APEX already has an end-to-end learning and review loop; evaluator comparison is an extension of that loop.

**Suggested explanation (45–60 seconds):** “A learner chooses a difficult-conversation case, speaks with the virtual patient, and APEX stores an ordered transcript. The selected evaluator produces communication feedback, selected metrics add research signals, and both learners and administrators review the result. Administrators also manage cases and see frozen plugin provenance. The comparison work reuses the completed transcript; it does not replace this workflow.”

**Important caveat:** A normal application run still depends on configured services such as the database and providers. Only this briefing and the seeded baseline case-study command are offline fallbacks.

**Question to ask:** “Which part of this workflow should the EACL demo spend the most time showing?”

**Transition:** “A synthetic encounter makes the evaluation problem concrete.”

### 3. Synthetic case and transcript — one realistic conversation

**Main message:** The fixture deliberately contains both strong behaviors and a repairable miss, making it useful for evaluator comparison.

**Suggested explanation (60–90 seconds):** “This is a wholly fictional lymphoma conversation. Turn 2 contains fear and a family concern. Turn 3 moves into diagnosis and jargon without acknowledging that fear. The patient names the miss at turn 4; the clinician repairs it at turn 5, asks permission, explains in plain language, checks understanding, elicits priorities, summarizes next steps, and invites questions. Stable turn numbers let every evaluator point to the same evidence.”

**Important caveat:** It is not clinical data, a private example, or evidence that any evaluator performed correctly.

**Question to ask:** “Does this fixture contain enough observable opportunities for expert review without becoming clinically over-specific?”

**Transition:** “APEX’s original frameworks look at different parts of this conversation.”

### 4. Original APEX foundations — SPIKES and AFCE

**Main message:** ACE-CT-inspired evaluation is additive; SPIKES and AFCE retain distinct educational roles.

**Suggested explanation (60 seconds):** “SPIKES gives APEX a structure for difficult-news communication: setting, perception, invitation, knowledge, emotion, and strategy/summary. AFCE focuses on appraisal and empathic discourse: opportunities, elicitations, responses, misses, and linked spans. ACE-CT-inspired work explores broader communication behaviors, but it does not make SPIKES or AFCE obsolete.”

**Important caveat:** Overlap does not make the frameworks equivalent or interchangeable.

**Question to ask:** “Is this distinction faithful to how you would position AFCE and ACE-CT together?”

**Transition:** “The plugin boundary lets these different responsibilities coexist cleanly.”

### 5. Plugin architecture — generate, interpret, measure

**Main message:** Patient-model, evaluator, and metrics plugins have separate interfaces and lifecycle roles.

**Suggested explanation (60 seconds):** “The patient-model plugin generates behavior while the encounter is running. The evaluator interprets a completed session into feedback. The metrics plugin measures observable features for research and analytics. At startup, a fixed module list registers classes in an in-memory registry. Settings or case overrides resolve those keys and freeze them on the session. This gives experiments traceable identities without pretending every component does the same job.”

**Important caveat:** The registry uses explicit imports; there is no automatic filesystem discovery.

**Question to ask:** “Is this separation clear enough to support the system-demonstration story?”

**Transition:** “Here is the inventory actually registered on this branch.”

### 6. Current plugin inventory — what really exists

**Main message:** The current system has one patient model, four evaluators on this branch, and one metrics plugin; only ACE-CT-inspired is unmerged.

**Suggested explanation (60–75 seconds):** “DefaultLLMPatientModel is one plugin with OpenAI and Gemini provider adapters. Baseline is rule-only. Hybrid v1 is the settings default and merges the rule core with optional LLM review. Hybrid v2 uses three focused reviews and a 70/30 merge. ApexMetrics exposes current AFCE-style counts and SPIKES coverage. ACECTInspiredRubricEvaluator is version 0.1.0-experimental, gated, unvalidated, and present only on the feature branch.”

**Important caveat:** Provider adapters are not separate patient-model plugins, and registration does not mean clinical validation.

**Question to ask:** “Should the paper inventory every plugin, or focus the main text on the evaluator family?”

**Transition:** “The comparison infrastructure makes those evaluator differences inspectable.”

### 7. Non-persisting evaluator comparison — completed spine

**Main message:** Evaluators can run independently on one immutable transcript without altering the learner record.

**Suggested explanation (60–75 seconds):** “The service loads a completed session, computes a canonical transcript hash, and runs each requested evaluator independently. It captures runtime and allowlisted provenance. If one fails, the error is sanitized and the others remain. It verifies that the transcript hash did not change. JSON is canonical; CSV is a compact summary. Crucially, the comparison path does not persist feedback, metrics, session fields, or turns.”

**Important caveat:** Hybrid and ACE live runs can make paid provider calls; automation uses fakes unless live calls are explicitly authorized.

**Question to ask:** “Is non-persistence a requirement for all early ACE-CT review, or only the default?”

**Transition:** “The next screen shows what a read-only comparison UI could make visible.”

### 8. Illustrative evaluator comparison — UI specification

**Main message:** The comparison UI should expose construct, evidence, provenance, and limitations—not just a score.

**Suggested explanation (75–90 seconds):** “Every tab sees the same transcript. Baseline, hybrid v1, and hybrid v2 retain the APEX score shape. The ACE-CT-inspired tab preserves four proposed groups and all 11 dimensions. Partial dimensions are amber; pace is null because timing and delivery are unavailable. Clicking an evidence number highlights the transcript coordinate. Provider/model and runtime remain unavailable because this is a mock. The UI makes disagreement reviewable without declaring a winner.”

**Important caveat:** Every displayed value is invented for UI discussion. The compatibility fields are provisional engineering projections.

**Question to ask:** “What must be visible for expert review: full reasoning, concise evidence, confidence, limitations, or all four?”

**Transition:** “That interface only works if the framework relationships stay explicit.”

### 9. SPIKES, AFCE, and ACE-CT together — three lenses

**Main message:** Structure, empathic discourse, and broader communication quality can overlap while remaining non-equivalent constructs.

**Suggested explanation (45–60 seconds):** “SPIKES asks whether the conversation followed a useful difficult-news structure. AFCE asks where empathic opportunities and responses occurred. ACE-CT-inspired asks which broader communication behaviors are observable in the transcript and where the modality limits are. Their evidence may overlap, but their meanings are different.”

**Important caveat:** Reusing an APEX SPIKES score in the ACE-shaped compatibility output does not make SPIKES an ACE-CT dimension.

**Question to ask:** “Should the compatibility view exist at all, or should the interface keep native framework outputs entirely separate?”

**Transition:** “That distinction is also central to the confidential-manuscript boundary.”

### 10. Paper architecture versus APEX — provenance boundary

**Main message:** APEX built an original integration and comparison path; it did not reproduce the manuscript’s research assets or model.

**Suggested explanation (60–75 seconds):** “At a permitted high level, the authorized manuscript involved private encounters, human ratings, transcript preprocessing, and several research-model directions evaluated against ratings. APEX starts from a learner’s virtual-patient session, projects the transcript strictly, applies a versioned provisional rubric through an injected provider, and returns evidence-backed results through a non-persisting comparison artifact. We adopted the framework direction, not private data, trained models, weights, examples, results, or exact unpublished anchors.”

**Important caveat:** Do not elaborate beyond the permitted high-level description or show the confidential source.

**Question to ask:** “Is the current provenance sentence sufficient, and what may be stated in a public paper, PR, or demo?”

**Transition:** “With that boundary clear, here is the precise engineering state.”

### 11. Completed engineering status — main versus feature branch

**Main message:** The stable contribution and the experimental extension are cleanly separable.

**Suggested explanation (60 seconds):** “Main contains non-persisting computation, the three established evaluator comparisons, hashing, provenance, runtime, failure isolation, exports, the seeded offline case-study path, tests, and documentation. The ACE branch adds strict projection, the provisional rubric and typed result, provider-independent evaluation, gating, comparison integration, synthetic review artifacts, and non-live verification. It does not add the real comparison page to the production frontend.”

**Important caveat:** Passing automated tests is technical verification, not clinical or construct validation.

**Question to ask:** “Which feature-branch pieces should be eligible to merge before scientific approval, if any?”

**Transition:** “The architecture supports many future plugins, but the roadmap must be sequenced.”

### 12. Literature-backed plugin roadmap — broad ideas, disciplined timing

**Main message:** The literature suggests a rich roadmap across all three plugin families, but most candidates belong after EACL.

**Suggested explanation (75–90 seconds):** “Patient candidates include minimal adaptive state, service-flow awareness, emotion-aware behavior, mental-health specialization, and speech-to-speech. Evaluator candidates include intent-oriented empathy, non-emotion-centric empathy, simulation quality, and data-dependent supervised ACE-CT directions. Near-term metrics are more feasible: transcript dynamics, jargon/readability, question and understanding checks, and evidence grounding. Stability and patient consistency are stretch work; service-flow and audio metrics are longer-term.”

**Important caveat:** These are title- and note-grounded inspirations, not claims that APEX implemented or reproduced the cited methods or findings.

**Question to ask:** “Which one future direction best strengthens the EACL discussion without becoming a promised deliverable?”

**Transition:** “The recommended implementation scope is narrower than the research roadmap.”

### 13. Recommended pre-EACL scope — smallest defensible demo

**Main message:** Reliability, decisions, inspectability, and frozen provenance matter more than new plugin count.

**Suggested explanation (60–75 seconds):** “First restore the complete application. Resolve the ACE scientific/disclosure questions. Run minimal controlled provider smoke tests. Build the read-only comparison UI. Add deterministic evidence metrics only if there is time. Create a small expert-reviewed set. Freeze everything by the analysis deadline, then produce the paper, architecture figure, video, and offline fallback. Treat minimal adaptive-patient state as stretch only after the core works.”

**Important caveat:** Scope reduction does not lower the research ambition; it protects the validity and reproducibility of the submitted system.

**Question to ask:** “Do you agree that the comparison platform is sufficient without another large patient or evaluator plugin?”

**Transition:** “The remaining calendar makes that sequencing necessary.”

### 14. EACL package and timeline — freeze before writing the final story

**Main message:** Scientific decisions and integrated validation must precede analysis freeze and submission production.

**Suggested explanation (45–60 seconds):** “Use the first week for decisions, application restoration, controlled live tests, and comparison UI. Use the next days for the small validation set. Freeze analysis, prompts, rubric, provider/model, and fixtures around September 12. Then finish the paper, architecture figure, demonstration media, and fallback. Reserve September 19–22 for claims, confidentiality, reproducibility, and submission checks.”

**Important caveat:** The official call remains authoritative for format, page limits, media, anonymity, and mechanics.

**Question to ask:** “Is the proposed analysis-freeze date realistic, and which review must occur before it?”

**Transition:** “The final slide turns the plan into decisions and owners.”

### 15. Decisions required today — close with commitments

**Main message:** Record explicit decisions, unresolved blockers, owners, and dates; do not leave scientific assumptions implicit.

**Suggested explanation (60–90 seconds):** “We need confirmation or correction of the four groups and 11 dimensions, the exact rubric source, partial-observability and null handling, aggregation, compatibility, naming, disclosure, provider/model, validation material, EACL framing, persistence scope, and owners/dates. My proposed default is comparison-only ACE output with explicit provenance and limitations until the controlling rubric and disclosure boundaries are confirmed.”

**Important caveat:** The checkboxes are discussion aids. The signed record is `decision-record.md`, and blank outcomes must stay blank until agreed.

**Question to ask:** “Which decision is blocking us most, and can we resolve it before ending?”

**Transition:** Move from slides to the decision record; read back owners, dates, and next checkpoint.

## Likely questions and concise answers

### Wasn’t APEX originally SPIKES-based?

Yes. SPIKES remains the difficult-conversation structure in APEX, and AFCE remains central to empathic opportunity/response analysis. The evaluator-comparison work adds an experimentation layer around the same completed transcript; it does not erase those foundations.

### Is ACE-CT replacing SPIKES?

No. They answer different questions. SPIKES concerns conversation structure; the ACE-CT-inspired experiment concerns broader communication behaviors. The APEX SPIKES field in compatibility output is explicitly external to ACE-CT and provisional.

### Did we reproduce the anonymous paper?

No. The authorized manuscript helped identify a promising framework direction and motivated transcript-based experimentation. APEX did not reproduce private data, models, weights, results, examples, or exact unpublished scoring anchors. The implementation is an original, gated, high-level transcript rubric and comparison integration.

### Is the evaluator clinically validated?

No. It is labeled `experimental_unvalidated`, uses provisional placeholder wording, and is intended for methodological review. Automated tests verify software behavior, not clinical validity or communication competence.

### Why compare multiple evaluators?

Comparison makes assumptions, evidence, score differences, provenance, and failure modes visible on the same transcript. It supports technical and expert review without overwriting the learner’s canonical record or declaring an evaluator superior without reference labels.

### Why is non-persistence important?

It prevents experiments from changing saved feedback, metrics, session fields, or turns. That isolates research comparison from the learner record, makes reruns safer, and allows failed evaluators to be inspected without corrupting canonical state.

### What works without Supabase?

This HTML package works entirely offline. The repository’s seeded baseline case-study command uses ephemeral in-memory SQLite and no model calls. The normal APEX application workflow still needs its configured backend/database environment.

### What still needs real OpenAI/Gemini calls?

Hybrid v1/v2 need OpenAI for their live LLM review paths. The ACE-CT-inspired evaluator supports OpenAI or Gemini through an injected adapter. Real calls should occur only after authorization, with exact provider/model/prompt/rubric provenance frozen and recorded.

### What is realistic by September 22?

A restored end-to-end app, approved boundaries, a read-only comparison UI, minimal authorized provider smoke tests, a small expert-reviewed synthetic/authorized set, frozen provenance, and a paper/demo package with an offline fallback. Several new large plugins are not realistic or necessary.

### What would be demonstrated at EACL?

A learner conducts a synthetic virtual-patient conversation; the completed transcript is compared across versioned evaluators without persistence; the interface exposes scores, evidence turns, provenance, runtime/failure state, and framework-specific limitations; artifacts can be exported; and the demo continues with a sanitized offline fallback if services are unavailable.

## Presenter safety checklist

- Keep the “Internal review” label visible.
- Do not screen-share the confidential PDF or private notes.
- Repeat “illustrative mock output” before discussing scores.
- Do not describe automated test success as scientific validation.
- Do not imply EACL acceptance, submission completion, or production UI completion.
- Record decisions and owners only after explicit agreement.

