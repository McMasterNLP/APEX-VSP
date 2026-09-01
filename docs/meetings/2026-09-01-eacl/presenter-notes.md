# APEX / EACL 2027 Presenter Notes

**Meeting:** September 1, 2026 internal working session with Dr. Allison Lahnala
**Presentation:** apex-eacl-briefing.html
**Primary goal:** Make the implemented architecture, scientific boundaries, expansion options, and EACL obligations concrete enough for Dr. Lahnala to shape APEX’s research identity and submission story.

## Delivery posture

Assume familiarity with APEX. Avoid re-pitching the application or narrating project status. Use the stable synthetic transcript as the common evidence surface, separate implemented behavior from proposed directions, and invite correction whenever the framing crosses a scientific boundary.

## Slide 1 — Today’s walkthrough

**Message:** We will move quickly from the familiar workflow into the research questions.

**Say:** “I want to use the same transcript all the way through: first to make the original APEX architecture visible, then to show the experimental comparison path, then to ask which research direction should lead the EACL story.”

**Ask:** “Is there one part you want to protect extra time for?”

**Transition:** “I’ll spend one slide on the familiar learner flow, then move to the evidence surface.”

## Slide 2 — Quick APEX refresher

**Message:** APEX joins virtual-patient practice with evidence-linked review.

**Say:** “The familiar flow is case selection, a stage-aware virtual-patient conversation, encounter completion, feedback and metrics, and learner/admin review. Today’s focus is the architecture under that surface.”

**Ask:** “Is this still the right one-sentence description of the application?”

**Transition:** “The stored transcript is what connects the experience to every evaluator.”

**Sources:** Repository README and implemented case, dialogue, scoring, and admin paths.

## Slide 3 — Stable synthetic transcript

**Message:** One fictional 12-turn encounter gives every lens the same evidence.

**Say:** “Turn 2 creates an explicit fear opportunity. Turn 3 moves to diagnosis and jargon without responding. Turn 5 repairs that miss and asks permission. Turns 7–11 add plain language, an understanding check, priorities, summary, next steps, and a question invitation.”

**Ask:** “Do these markers separate observable behavior from interpretation clearly enough?”

**Transition:** “The original APEX foundations explain how those turns become structured signals.”

**Source:** assets/synthetic-transcript.json. Entirely synthetic; not clinical data.

## Slide 4 — Original foundations

**Message:** SPIKES and AFCE-aligned signals are complementary inputs to scoring and feedback.

**Required explanation:** “AFCE-aligned detectors and relations are implemented. ApexMetrics exposes selected measures. Baseline and hybrid evaluators use those signals. AFCE is not a standalone evaluator.”

**Required boundary:** “APEX implements an AFCE-aligned, rule-based operationalization of selected constructs.”

**Say:** “On one side, SPIKES captures difficult-news conversation structure. On the other, rules detect selected Feeling, Judgment, and Appreciation opportunities, elicitations, response forms, and turn-linked misses. APEX combines those signals into scores, timeline events, suggestions, and research measures.”

**Ask:** “Is the AFCE-aligned description faithful and appropriately narrow?”

**Transition:** “Now I’ll place those two analytical flows inside the full running system.”

**Sources:** docs/research/afce_framework.md; docs/research/spikes_protocol.md; Lahnala et al. 2024.

## Slide 5 — Original system architecture

**Message:** Patient generation is live, while evaluation starts from the ordered stored encounter.

**Say:** “Case configuration and session state feed the selected patient-model plugin. The conversation produces an ordered transcript with frozen plugin provenance. NLU/span analysis creates SPIKES and AFCE-aligned signals. The selected evaluator and metrics plugins produce feedback for the UI.”

**Emphasize:** “Production persistence and the research comparison are separate. The normal learner workflow may persist feedback and metrics. The comparison path reads a completed transcript and computes alternatives in memory.”

**Ask:** “For the paper, should the learner loop or the inspectable research loop lead this figure?”

**Transition:** “The experimental ACE-CT-inspired evaluator is one explicit consumer of that stored transcript.”

**Sources:** backend plugin interfaces/registry, default patient model, NLU adapters, scoring service, evaluator comparison service.

## Slide 6 — ACE-CT-inspired evaluator

**Message:** The evaluator is a provider-neutral, versioned, strict transcript-rubric experiment—not an official ACE-CT implementation.

**Say:** “The service projects roles strictly, applies a versioned rubric, calls an injected OpenAI or Gemini adapter, validates typed output, and preserves scores, evidence, confidence, and limitations across four groups and 11 dimensions.”

**Emphasize:** “Respond to emotion, avoiding interruption/diversion, and pace are only partly observable from text. Tone, silence, overlap timing, and non-verbal behavior are unavailable. The General group and all anchors remain pending expert review.”

**Ask:** “Is this four-group, 11-dimension structure an appropriate object for expert review, or should the research unit be narrower?”

**Transition:** “The next slide shows why we kept this work separate from canonical learner feedback.”

**Sources:** docs/research/ace_ct_inspired_evaluator_design.md; public ACE-CT article, DOI 10.1016/j.pec.2025.109465; authorized confidential manuscript, public citation pending expert confirmation.

## Slide 7 — Non-persisting comparison flow

**Message:** The same completed transcript can be compared without overwriting the learner record.

**Say:** “Baseline, Hybrid v1, Hybrid v2, and the explicitly selected ACE-CT-inspired evaluator produce a canonical comparison artifact. The comparison does not write feedback, session metrics, turns, or plugin selections.”

**Emphasize:** “ACE-CT-inspired is excluded from the aggregate all option, evidence turns must exist, and provider/model/rubric provenance travels with each result.”

**Ask:** “Is comparison-only the right default boundary while the experimental rubric is reviewed?”

**Transition:** “Here is the interface concept that makes that comparison inspectable.”

**Sources:** docs/research/evaluator_comparison.md; docs/research/ace_ct_inspired_evaluator_design.md.

## Slide 8 — Interactive illustrative comparison

**Message:** A useful research interface aligns scores, narrative findings, evidence, provenance, and limitations.

**Demo:** Select each evaluator tab. Use evidence buttons to highlight the same transcript turns. On ACE-CT-inspired, point to the null pace dimension and the modality limitation.

**Say:** “These values are invented UI examples. They do not show evaluator accuracy, learner competence, clinical quality, or relative validity. No model was run.”

**Ask:** “What would you need beside this comparison to make it scientifically useful: expert labels, disagreement views, repeated runs, or another evidence form?”

**Transition:** “The interface should preserve the fact that these lenses overlap without being equivalent.”

**Source:** assets/illustrative-comparison.json.

## Slide 9 — Three complementary lenses

**Message:** SPIKES, AFCE-aligned signals, and ACE-CT-inspired assessment cannot be collapsed into one framework.

**Say:** “SPIKES asks about difficult-news structure. AFCE-aligned signals ask where appraisal-linked opportunities and responses occur. The ACE-CT-inspired rubric asks about a broader set of communication behaviors visible in the transcript.”

**Emphasize:** “The compatibility bridge is an engineering display mapping, not an official theoretical crosswalk and not a replacement claim.”

**Ask:** “How should the paper describe the overlap without over-integrating the constructs?”

**Transition:** “The plugin model gives us a clean way to keep these responsibilities separate.”

## Slide 10 — Extensibility model

**Message:** APEX Core owns workflow and provenance; plugins own bounded behavior through three interfaces.

**Say:** “Patient-model plugins generate one response from case/session state and clinician input. Evaluator plugins evaluate a completed session. Metrics plugins calculate additional research measures. Registration is deterministic, the session selection is frozen, provider and NLU adapters remain implementation details, and experimental plugins are opt-in.”

**Ask:** “Does this separation support the research platform story, or should the EACL story hide some of this machinery?”

**Transition:** “The implemented inventory is small enough to explain concretely.”

**Sources:** backend/src/interfaces; backend/src/plugins/registry.py; backend/src/plugins/load_plugins.py.

## Slide 11 — Implemented plugins

**Message:** The current plugins are concrete wrappers around the live patient, scoring, and metrics paths.

**Say:** “DefaultLLMPatientModel builds a case- and stage-aware prompt and delegates to an OpenAI or Gemini adapter. Baseline is rule-only. Hybrid v1 adds one optional LLM review; Hybrid v2 uses three focused reviews and the existing merge policy. ACE-CT-inspired is experimental and unmerged. ApexMetrics exposes selected opportunity/response counts and SPIKES coverage.”

**Required AFCE explanation:** “AFCE-aligned detectors/relations are implemented; ApexMetrics exposes selected measures; baseline/hybrids use the signals; AFCE is not a standalone evaluator.”

**Ask:** “Which of these components represents APEX’s most distinctive contribution today?”

**Transition:** “The public literature suggests several directions we could attach without pretending they are already part of APEX.”

**Sources:** implemented plugin modules and scoring service.

## Slide 12 — Literature-inspired expansion directions

**Message:** Ten public sources open several research directions, but the slide makes no feasibility or commitment claim.

**Say:** “Adaptive-VP suggests trainee-responsive patient state. SFMSS suggests service-flow control. PATIENT-ψ suggests domain-bounded mental-health simulation. Emotion-aware dialogue suggests an explicit affect loop. Empathy-intent and non-emotion-centric work suggest alternative evaluator constructs. Speech-to-speech work suggests an audio interaction path. The medical-dialogue survey suggests broader system-quality evaluation. The 2022 and 2024 Lahnala papers anchor construct clarity, validity, and discourse-level empathy analysis.”

**Ask:** “Which of these directions strengthens APEX’s identity rather than simply adding features?”

**Transition:** “Grouped by the existing interfaces, the candidate space looks like this.”

**Sources:** The ten linked ACL Anthology records on the slide. Use “inspired by”; do not imply reproduction.

## Slide 13 — Possible next plugins

**Message:** Patient, evaluator, and metrics additions can be discussed independently.

**Say:** “The point is not to rank or schedule these today. It is to identify which family should carry the next research contribution and which measures would make that contribution credible.”

**Ask exactly:** “Which additions best match the intended research identity of APEX?”

**Transition:** “That choice should also respond directly to the official System Demonstrations review criteria.”

## Slide 14 — EACL expectations and preparation phases

**Message:** The current official call requires all three submission components and evidence supporting the prototype.

**Say:** “The verified call requires a paper of up to six pages, a demo video of at most two and a half minutes, and a live site or installable package. It asks for motivation and novelty, related work, technical detail and visuals, system/demo description, some evidence of usefulness or quality, availability/licensing, and ethics. It also requires a reciprocal reviewer nomination. If accepted, a registered author presents a live demo with a poster.”

**Say:** “The preparation phases deliberately have outcomes but no internal dates or owners: settle the science, restore the application, test end to end, run controlled provider tests, refine the experiment, build the comparison view, obtain a small expert-reviewed evaluation, freeze provenance, assemble the package, and review every claim.”

**Ask:** “What is the smallest evidence package you would regard as credible for this submission?”

**Transition:** “I want to end with the larger question of what APEX should become for this venue.”

**Source:** Official EACL 2027 Systems Demonstrations call: https://2027.eacl.org/calls/demos/

## Slide 15 — Dr. Lahnala’s vision and discussion

**Message:** The meeting should end with a research direction, not a checklist exercise.

**Facilitate:** Move through research direction, scientific design, application direction, and submission expectations. Capture only explicitly agreed outcomes in decision-record.md after the discussion.

**Provider point:** Gemini is immediately available to Christian for controlled tests; OpenAI may require restoration. Treat the default/provider choice as open, with reproducibility and fallback needs in view.

**Ask exactly:** “What does the strongest realistic version of APEX look like for this EACL submission?”

**Note:** The on-slide text area has no save or submit behavior. Do not put sensitive or confidential details into a screen-shared browser field.

## Ten-minute fallback walkthrough

1. **Slide 1 (30 sec):** State that the goal is to shape the EACL research identity.
2. **Slide 3 (60 sec):** Show the fear opportunity at turn 2, miss at turn 3, repair at turn 5, and structured close at turn 11.
3. **Slides 4–5 (90 sec):** Give the exact AFCE boundary, then explain live patient generation versus stored evaluation.
4. **Slides 6–7 (90 sec):** Explain the strict ACE-CT-inspired pipeline, partial observability, and the no-overwrite comparison boundary.
5. **Slide 8 (60 sec):** Open ACE-CT-inspired, highlight turns 3 and 5, and state that every value is illustrative.
6. **Slides 10–11 (90 sec):** Show the three plugin families and the implemented patient/evaluator/metrics paths.
7. **Slides 12–13 (60 sec):** Name the main literature lanes and ask which family best fits the research identity.
8. **Slide 14 (60 sec):** State the three mandatory submission components, evidence expectation, reciprocal reviewer, and ethics obligation.
9. **Slide 15 (60 sec):** Ask for the strongest realistic APEX vision and capture agreed follow-up outside the slide.

## Non-negotiable boundaries

- Synthetic transcript only; no clinical or confidential example.
- Comparison values are illustrative, never observed results.
- AFCE-aligned implementation is partial and rule-based; AFCE is not a standalone evaluator.
- ACE-CT-inspired work is experimental, unvalidated, non-default, and pending expert review.
- No private data, models, weights, results, examples, or unpublished anchors are reproduced.
- No live LLM call occurred in preparing this package.
- The presentation branch changes documentation only; it does not change production code.
