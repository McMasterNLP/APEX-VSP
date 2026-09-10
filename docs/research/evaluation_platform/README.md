# APEX research evaluation platform

This package documents Item 1 of the APEX research evaluation platform: a
lossless, capability-driven result path for read-only evaluator research. It is
additive to the learner feedback workflow and does not change saved feedback,
session state, turns, metrics, or plugin selection.

## Current scope

Item 1 provides a versioned `ResearchEvaluationEnvelope`, typed
framework-native results, deterministic research adapters, normalized research
projections, explicit capability manifests, an admin-only non-persisting API,
sanitized JSON and multi-table CSV exports, and a read-only workspace in the
administrator Session Logs workflow.

Implemented evaluator families are:

- APEX baseline, using the existing SPIKES and AFCE-aligned rule computation;
- APEX hybrid v1 and hybrid v2, preserving their complete validated APEX
  feedback result and LLM-review metadata when live execution is authorized;
- the experimental ACE-CT-inspired evaluator, retaining all eleven dimensions,
  four proposed domain aggregates, assessability, evidence, limitations, and
  compatibility projections.

APEX empathy processing is described consistently as an **AFCE-aligned,
rule-based operationalization of selected constructs**. It is not a complete or
validated AFCE reproduction. The ACE-CT-inspired evaluator is experimental,
unvalidated, non-official, and is not a reproduction of the confidential
manuscript's trained models.

## Architecture summary

```text
canonical transcript
        |
        v
explicitly selected evaluator --> validated framework-native result
                                      | (authoritative)
                                      v
                              deterministic research adapter
                                      |
                                      v
                         normalized research projection
                                      |
                        +-------------+-------------+
                        |             |             |
                    admin UI       comparison     exports
```

The framework-native result is authoritative. The projection is a derived,
generic representation and never replaces framework semantics. Capability
manifests determine which generic UI and export sections apply; evaluator names
do not determine generic rendering.

## Terminology

- **ResearchEvaluationEnvelope**: the complete research-facing result for one
  evaluation run.
- **Framework-native result**: the typed authoritative evaluator output.
- **Research adapter**: a deterministic translator from a native result to a
  projection.
- **Research projection**: typed spans, turn labels, relations, ratings,
  metrics, findings, and limitations used by generic consumers.
- **Capability manifest**: declared supported outputs and future annotation
  operations.
- **Evaluation run**: one evaluator/configuration applied to one canonical
  transcript.
- **Source reference**: a safe structured link from a projected object to an
  authoritative native field.

## Documentation map

- [Architecture](architecture.md)
- [Result contract](result_contract.md)
- [Evaluator integration guide](evaluator_integration_guide.md)
- [API and UI workflow](api_and_ui_workflow.md)
- [Provenance and reproducibility](provenance_and_reproducibility.md)
- [Privacy, security, and ethics](privacy_security_and_ethics.md)
- [Testing and validation](testing_and_validation.md)
- [Limitations and future work](limitations_and_future_work.md)
- [Paper evidence guide](paper_evidence_guide.md)
- [Architecture decision records](adr/)

## Future Items 2 and 3

Item 2 will add durable human review concepts such as annotation sets,
confirm/reject/correct actions, span and rating changes, reviewer attribution,
and adjudication. Item 3 will add evaluator validation runs, gold datasets,
precision/recall/F1 and agreement analyses, and validation dashboards. Neither
item is implemented or implied by the read-only declarations in Item 1.

Arbitrary plugin uploads, dynamic execution of researcher-supplied code, and
unreviewed external inference endpoints remain prohibited.
