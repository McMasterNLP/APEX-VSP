# APEX research evaluation platform

This package documents Item 1's lossless, capability-driven evaluator result
path and Item 2A's durable human review workspace. Both are additive to the
learner feedback workflow and do not change saved feedback, session state,
turns, metrics, or plugin selection.

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
- **Capability manifest**: declared supported outputs and projection-specific
  annotation operations.
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
- [Human annotation workspace](annotation_workspace.md)
- [Annotation contract](annotation_contract.md)
- [Annotation API and UI](annotation_api_and_ui.md)
- [Annotation export format](annotation_export_format.md)
- [Architecture decision records](adr/)

## Item 2A and future work

Item 2A adds immutable saved runs, reviewer-specific annotation sets,
confirm/reject/typed-correction actions, append-only history, locking/reopening,
and reviewed-projection exports. It does not add span-boundary editing,
human-added false negatives, multiple-reviewer adjudication, or agreement.
Item 3 will add evaluator validation runs, complete reference datasets,
precision/recall/F1 and agreement analyses, and validation dashboards. Neither
validation nor complete-gold claims are implied by Item 2A.

Arbitrary plugin uploads, dynamic execution of researcher-supplied code, and
unreviewed external inference endpoints remain prohibited.
