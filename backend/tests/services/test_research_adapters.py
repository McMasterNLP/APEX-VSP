"""Mapping coverage tests for built-in research-result adapters."""

from domain.models.evaluator_comparison import (
    EvaluatorRunResult,
    EvaluatorScores,
)
from domain.models.scoring import ComputedFeedback
from domain.models.sessions import SuggestedResponse, TimelineEvent
from domain.models.research_evaluation import (
    ACECTNativeResearchResult,
    ApexFeedbackNativeResult,
    ResearchTranscriptTurn,
    validate_projection_against_transcript,
)
from schemas.ace_ct import ACECTEvaluationResult
from services.ace_ct_results import (
    build_ace_ct_framework_results,
    project_ace_ct_compatibility_scores,
)
from services.evaluator_comparison_service import build_evaluator_provenance
from services.research_adapters.ace_ct import (
    ACECTResearchAdapter,
    ACE_FRAMEWORK_FIELD_MAPPING,
)
from services.research_adapters.apex import (
    APEX_COMPUTED_FEEDBACK_FIELD_MAPPING,
    ApexResearchAdapter,
)
from services.research_adapters.base import ResearchAdapterContext
from services.transcript_identity import hash_transcript
from tests.utils.ace_ct import build_valid_ace_ct_payload


def _turns() -> tuple[ResearchTranscriptTurn, ...]:
    return (
        ResearchTranscriptTurn(
            turn_number=1,
            role="clinician",
            source_role="user",
            text="How are you feeling?",
        ),
        ResearchTranscriptTurn(
            turn_number=2,
            role="patient",
            source_role="assistant",
            text="I feel worried.",
        ),
        ResearchTranscriptTurn(
            turn_number=3,
            role="clinician",
            source_role="user",
            text="I understand.",
        ),
    )


def _context(evaluator_identifier: str, framework: str) -> ResearchAdapterContext:
    turns = _turns()
    source_turns = [
        {
            "turn_number": turn.turn_number,
            "role": turn.source_role,
            "text": turn.text,
        }
        for turn in turns
    ]
    return ResearchAdapterContext(
        transcript_hash=hash_transcript(source_turns),
        transcript_turns=turns,
        evaluator_identifier=evaluator_identifier,
        framework_identifier=framework,
    )


def _computed_feedback(*, phase: str = "baseline_rule_v1") -> ComputedFeedback:
    return ComputedFeedback(
        session_id=987,
        empathy_score=80,
        communication_score=75,
        spikes_completion_score=50,
        overall_score=70,
        eo_counts_by_dimension={
            "Feeling": {"explicit": 1, "implicit": 0},
            "Judgment": {"explicit": 0, "implicit": 0},
            "Appreciation": {"explicit": 0, "implicit": 0},
        },
        elicitation_counts_by_type={
            "direct": {"Feeling": 1, "Judgment": 0, "Appreciation": 0},
            "indirect": {"Feeling": 0, "Judgment": 0, "Appreciation": 0},
        },
        response_counts_by_type={
            "understanding": 1,
            "sharing": 0,
            "acceptance": 0,
        },
        linkage_stats={
            "total_eos": 1,
            "addressed_count": 1,
            "missed_count": 0,
            "addressed_rate": 1.0,
            "missed_rate": 0.0,
        },
        missed_opportunities_by_dimension={
            "Feeling": 0,
            "Judgment": 0,
            "Appreciation": 0,
        },
        eo_to_elicitation_links={
            "eo_1": [
                {
                    "source_span_id": "eo_1",
                    "target_span_id": "elic_2",
                    "relation_type": "elicits",
                    "confidence": 0.85,
                }
            ]
        },
        eo_to_response_links={
            "eo_1": [
                {
                    "source_span_id": "eo_1",
                    "target_span_id": "resp_2",
                    "relation_type": "responds_to",
                    "confidence": 0.9,
                }
            ]
        },
        missed_opportunities=[],
        eo_spans=[
            {
                "span_type": "eo",
                "turn_number": 2,
                "turn_id": 123,
                "dimension": "Feeling",
                "explicit_or_implicit": "explicit",
                "start_char": 7,
                "end_char": 14,
                "text": "worried",
                "confidence": 0.9,
                "provenance": "rule",
            }
        ],
        elicitation_spans=[
            {
                "span_type": "elicitation",
                "turn_number": 1,
                "turn_id": 122,
                "type": "direct",
                "dimension": "Feeling",
                "start_char": 0,
                "end_char": 19,
                "text": "How are you feeling",
                "confidence": 0.9,
                "provenance": "rule",
            }
        ],
        response_spans=[
            {
                "span_type": "response",
                "turn_number": 3,
                "turn_id": 124,
                "type": "understanding",
                "start_char": 2,
                "end_char": 12,
                "text": "understand",
                "confidence": 0.8,
                "provenance": "rule",
            }
        ],
        spikes_coverage={"covered": ["perception", "emotion"], "percent": 2 / 6},
        spikes_timestamps={"perception": {"start_ts": "2026-09-01T00:00:00Z"}},
        spikes_strategies={"emotion": [{"strategy": "validate", "turn": 3}]},
        question_breakdown={"open": 1, "closed": 0, "eliciting": 1, "ratio_open": 1},
        bias_probe_info=None,
        evaluator_meta={
            "phase": phase,
            "status": "completed" if phase != "baseline_rule_v1" else "offline",
            "llm_output": (
                {"stage_turn_mapping": [{"turn_number": 3, "stage": "emotion"}]}
                if phase != "baseline_rule_v1"
                else None
            ),
        },
        latency_ms_avg=4.5,
        strengths="The clinician acknowledged emotion.",
        areas_for_improvement="Invite more detail.",
        detailed_feedback="Overall Score: 70.0/100",
        timeline_events=[
            TimelineEvent(turn_number=1, type="spikes", label="SPIKES Perception"),
            TimelineEvent(turn_number=2, type="eo", label="Empathy Opportunity"),
            TimelineEvent(turn_number=3, type="response", label="Empathy Response"),
        ],
        suggested_responses=[
            SuggestedResponse(
                turn_number=2,
                patient_text="I feel worried.",
                suggestion="Tell me more about what worries you.",
            )
        ],
    )


def _apex_run(identifier: str = "baseline") -> EvaluatorRunResult:
    context = _context(identifier, "apex-spikes-afce")
    return EvaluatorRunResult(
        evaluator_identifier=identifier,
        evaluator_name="ApexEvaluator",
        evaluator_version="1.0",
        status="success",
        runtime_ms=2.5,
        transcript_hash=context.transcript_hash,
        provenance=build_evaluator_provenance(identifier),
        scores=EvaluatorScores(
            empathy_score=80,
            communication_score=75,
            spikes_completion_score=50,
            overall_score=70,
        ),
        structured_feedback=_computed_feedback(
            phase="baseline_rule_v1" if identifier == "baseline" else f"{identifier}_review"
        ),
    )


def test_apex_mapping_preserves_spans_relations_scores_and_findings():
    context = _context("baseline", "apex-spikes-afce")
    adapter = ApexResearchAdapter(live_execution=False)
    native = adapter.build_native_result(_apex_run(), context)
    assert isinstance(native, ApexFeedbackNativeResult)
    assert native.scores.overall_score == 70
    assert native.eo_spans[0].text == "worried"
    assert native.eo_to_elicitation_links[0].relation_type == "elicits"
    assert native.eo_to_response_links[0].relation_type == "responds_to"
    assert native.spikes_coverage.covered == ("perception", "emotion")
    assert native.suggested_responses[0].suggestion.startswith("Tell me")
    assert "session_id" not in native.model_dump(mode="json")

    projection = adapter.project(native, context)
    validate_projection_against_transcript(projection, context.transcript_turns)
    assert len(projection.spans) == 3
    assert len(projection.relations) == 2
    assert {metric.metric_name for metric in projection.global_metrics} >= {
        "empathy_score",
        "communication_score",
        "spikes_completion_score",
        "overall_score",
    }
    assert {finding.finding_type for finding in projection.findings} >= {
        "strength",
        "improvement",
    }


def test_shared_hybrid_adapter_retains_evaluator_provenance_and_llm_metadata():
    context = _context("hybrid_v2", "apex-spikes-afce")
    adapter = ApexResearchAdapter(live_execution=True)
    native = adapter.build_native_result(_apex_run("hybrid_v2"), context)
    projection = adapter.project(native, context)
    assert native.evaluator_family == "hybrid_v2"
    assert native.evaluator_metadata["phase"] == "hybrid_v2_review"
    assert projection.turn_labels[0].turn_number == 3
    assert projection.turn_labels[0].subtype == "emotion"


def test_apex_mapping_table_covers_every_computed_feedback_field():
    assert set(ComputedFeedback.model_fields) == set(APEX_COMPUTED_FEEDBACK_FIELD_MAPPING)
    assert APEX_COMPUTED_FEEDBACK_FIELD_MAPPING["session_id"].startswith("not exported")


def test_ace_adapter_preserves_all_dimensions_domains_assessability_and_limitations():
    evaluation = ACECTEvaluationResult.model_validate(
        build_valid_ace_ct_payload(evidence_turn_numbers=[1, 2])
    )
    compatibility = project_ace_ct_compatibility_scores(
        evaluation, apex_baseline_spikes_completion_score=50
    )
    framework = build_ace_ct_framework_results(
        evaluation, compatibility_projection=compatibility
    )
    context = _context("ace_ct_inspired", "ace-ct-inspired")
    run = EvaluatorRunResult(
        evaluator_identifier="ace_ct_inspired",
        evaluator_name="ACECTInspiredRubricEvaluator",
        evaluator_version="0.1.0-experimental",
        status="success",
        runtime_ms=3,
        transcript_hash=context.transcript_hash,
        provenance=build_evaluator_provenance(
            "ace_ct_inspired",
            llm_provider="openai",
            model_identifier="synthetic-model",
        ),
        scores=compatibility.scores,
        framework_results=framework,
        compatibility_projection=compatibility,
    )
    adapter = ACECTResearchAdapter()
    native = adapter.build_native_result(run, context)
    assert isinstance(native, ACECTNativeResearchResult)
    assert len(native.framework_results.dimension_results) == 11
    assert len(native.framework_results.domain_scores) == 4
    assert native.framework_results.assessability_counts.text_assessable == 8
    assert native.framework_results.limitations.transcript_only is True
    assert native.publication_model_reproduction is False

    projection = adapter.project(native, context)
    validate_projection_against_transcript(projection, context.transcript_turns)
    assert len(projection.dimension_ratings) == 11
    assert {rating.domain_identifier for rating in projection.dimension_ratings} == {
        "respond",
        "listen",
        "speak",
        "general",
    }
    assert len([m for m in projection.global_metrics if m.metric_name.startswith("domain_")]) == 4
    compatibility_metrics = [
        metric
        for metric in projection.global_metrics
        if metric.metric_name.startswith("compatibility_")
    ]
    assert len(compatibility_metrics) == 4
    assert all("not framework-equivalent" in m.comparability_statement for m in compatibility_metrics)
    assert {limitation.code for limitation in projection.limitations} >= {
        "transcript_only_assessment",
        "experimental_unvalidated_rubric",
        "missing_audio",
        "missing_timing",
    }


def test_ace_mapping_table_covers_every_framework_field():
    from domain.models.evaluator_comparison import EvaluatorFrameworkResults

    assert set(EvaluatorFrameworkResults.model_fields) == set(ACE_FRAMEWORK_FIELD_MAPPING)
