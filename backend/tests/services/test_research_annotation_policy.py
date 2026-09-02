"""Framework-aware annotation policy and inventory tests."""

from core.time import serialize_utc_datetime, utc_now
from domain.models.research_evaluation import (
    ResearchEvaluationEnvelope,
    ResearchEvaluatorMetadata,
    ResearchProvenance,
    ResearchRunMetadata,
    ResearchTranscriptIdentity,
)
from services.research_adapters.base import ResearchAdapterContext
from services.research_adapters.defaults import build_default_research_adapter_registry
from services.research_annotation_policy import (
    APEX_GUIDELINE_IDENTIFIER,
    AnnotationPolicyError,
    eligible_prediction_inventory,
    policy_for_envelope,
    validate_requested_guideline,
)
from tests.services.test_research_adapters import _apex_run, _turns


def _apex_envelope() -> ResearchEvaluationEnvelope:
    registration = build_default_research_adapter_registry().get("baseline")
    turns = _turns()
    transcript_hash = _apex_run("baseline").transcript_hash
    context = ResearchAdapterContext(
        transcript_hash=transcript_hash,
        transcript_turns=turns,
        evaluator_identifier="baseline",
        framework_identifier=registration.framework.identifier,
    )
    native = registration.adapter.build_native_result(_apex_run("baseline"), context)
    projection = registration.adapter.project(native, context)
    timestamp = serialize_utc_datetime(utc_now())
    return ResearchEvaluationEnvelope(
        run=ResearchRunMetadata(
            run_id="run_" + "a" * 40,
            timestamp=timestamp,
            runtime_ms=1,
            execution_mode="offline",
            completion_status="success",
        ),
        transcript=ResearchTranscriptIdentity(
            canonical_transcript_hash=transcript_hash,
            turn_count=len(turns),
            raw_transcript_included=False,
        ),
        evaluator=ResearchEvaluatorMetadata(
            identifier="baseline",
            display_name=registration.display_name,
            version=registration.evaluator_version,
            evaluator_type="rule_based",
        ),
        framework=registration.framework,
        adapter=registration.adapter_metadata,
        capabilities=registration.capabilities,
        framework_result=native,
        projection=projection,
        status="success",
        provenance=ResearchProvenance(
            generated_at=timestamp,
            runtime_ms=1,
            live_execution=False,
        ),
    )


def test_apex_policy_inventory_is_projection_driven_and_excludes_metrics():
    envelope = _apex_envelope()
    policy = policy_for_envelope(envelope)
    inventory = eligible_prediction_inventory(envelope, policy)
    assert policy.guideline_identifier == APEX_GUIDELINE_IDENTIFIER
    assert {item.projection_type for item in inventory} == {
        "span_annotation",
        "turn_label",
        "relation",
        "finding",
    }
    assert not ({metric.metric_id for metric in envelope.projection.global_metrics} & {
        item.prediction_id for item in inventory
    })
    span_items = [item for item in inventory if item.projection_type == "span_annotation"]
    assert all(item.allowed_operations.adjust_span for item in span_items)
    assert policy.span_authoring.supported is True
    assert {item.relation_type for item in policy.relation_types} == {
        "responds_to",
        "elicits",
    }


def test_policy_rejects_incompatible_guideline_and_adapter_version():
    envelope = _apex_envelope()
    policy = policy_for_envelope(envelope)
    try:
        validate_requested_guideline(policy, "different-guideline", "1.0")
    except AnnotationPolicyError as error:
        assert "incompatible" in str(error)
    else:
        raise AssertionError("Expected incompatible guideline rejection")

    unsupported = envelope.model_copy(
        update={"adapter": envelope.adapter.model_copy(update={"version": "2.0"})}
    )
    try:
        policy_for_envelope(unsupported)
    except AnnotationPolicyError as error:
        assert "adapter version" in str(error)
    else:
        raise AssertionError("Expected unsupported adapter rejection")
