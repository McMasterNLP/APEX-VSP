"""Contract tests for versioned research-evaluation models."""

import pytest
from pydantic import ValidationError

from domain.models.research_evaluation import (
    AnnotationOperationCapabilities,
    DimensionRating,
    FRAMEWORK_NATIVE_RESULT_ADAPTER,
    ProjectedRelation,
    ResearchFinding,
    ResearchProjection,
    ResearchTranscriptTurn,
    SourceReference,
    SpanAnnotation,
    VersionedExtensionNativeResult,
    validate_projection_against_transcript,
)


def _source(path: str = "eo_spans[0]") -> SourceReference:
    return SourceReference(
        native_result_type="apex_feedback",
        native_identifier="apex-spikes-afce",
        native_path=path,
        adapter_version="1.0",
    )


def _span(**updates) -> SpanAnnotation:
    values = {
        "prediction_id": "span_" + "a" * 40,
        "framework_identifier": "apex-spikes-afce",
        "turn_number": 1,
        "start_offset": 0,
        "end_offset": 4,
        "quoted_text": "This",
        "label": "empathic_opportunity",
        "source_reference": _source(),
    }
    values.update(updates)
    return SpanAnnotation.model_validate(values)


def _rating(**updates) -> DimensionRating:
    values = {
        "rating_id": "rating_" + "b" * 40,
        "framework_identifier": "ace-ct-inspired",
        "dimension_identifier": "respond_to_emotion",
        "domain_identifier": "respond",
        "score": 4,
        "scale_minimum": 1,
        "scale_maximum": 5,
        "score_status": "available",
        "assessability": "partially_assessable",
        "confidence": 0.8,
        "evidence_turns": (1,),
        "rationale": "Evidence is present in the transcript.",
        "source_reference": SourceReference(
            native_result_type="ace_ct_inspired",
            native_identifier="ace-ct-inspired",
            native_path="framework_results.dimension_results[0]",
            adapter_version="1.0",
        ),
    }
    values.update(updates)
    return DimensionRating.model_validate(values)


def test_framework_native_discriminator_rejects_unknown_type():
    with pytest.raises(ValidationError):
        FRAMEWORK_NATIVE_RESULT_ADAPTER.validate_python(
            {"native_type": "raw_provider_json", "payload": {"score": 1}}
        )


def test_extension_contract_rejects_nested_arbitrary_provider_output():
    with pytest.raises(ValidationError):
        VersionedExtensionNativeResult.model_validate(
            {
                "provider_output_validated": True,
                "extension_identifier": "reviewed.intent-model",
                "extension_schema_version": "1.0",
                "fields": ({"name": "payload", "value": {"unvalidated": True}},),
            }
        )


def test_item_2_annotation_capabilities_keep_future_operations_disabled():
    capabilities = AnnotationOperationCapabilities(confirm=True, reject=True)
    assert capabilities.confirm is True
    assert capabilities.reject is True
    assert capabilities.adjust_span is False
    assert capabilities.add_annotation is False
    assert capabilities.add_relation is False
    with pytest.raises(ValidationError):
        AnnotationOperationCapabilities(adjust_span=True)


@pytest.mark.parametrize(
    "path",
    ["feedback.session_id", "metadata.user_id", "request.token", "person.email"],
)
def test_source_reference_rejects_private_identity_paths(path: str):
    with pytest.raises(ValidationError):
        _source(path)


def test_projection_rejects_broken_relation_endpoint():
    span = _span()
    relation = ProjectedRelation(
        relation_id="relation_" + "c" * 40,
        framework_identifier="apex-spikes-afce",
        source_annotation_id=span.prediction_id,
        target_annotation_id="span_" + "d" * 40,
        relation_type="responds_to",
        source_reference=_source("eo_to_response_links.eo_1[0]"),
    )
    with pytest.raises(ValidationError, match="target endpoint"):
        ResearchProjection(spans=(span,), relations=(relation,))


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"score": 6}, "outside"),
        ({"score": None, "score_status": "available"}, "requires a score"),
        (
            {"score": 3, "score_status": "insufficient_evidence"},
            "explicit null score",
        ),
    ],
)
def test_dimension_rating_scale_and_null_semantics(updates: dict, message: str):
    with pytest.raises(ValidationError, match=message):
        _rating(**updates)


def test_transcript_validation_checks_offsets_and_exact_quote():
    transcript = (
        ResearchTranscriptTurn(
            turn_number=1,
            role="patient",
            source_role="assistant",
            text="This is difficult.",
        ),
    )
    validate_projection_against_transcript(ResearchProjection(spans=(_span(),)), transcript)

    bad_quote = _span(quoted_text="That")
    with pytest.raises(ValueError, match="quoted text"):
        validate_projection_against_transcript(
            ResearchProjection(spans=(bad_quote,)), transcript
        )

    bad_end = _span(end_offset=200, quoted_text="This")
    with pytest.raises(ValueError, match="exceeds"):
        validate_projection_against_transcript(
            ResearchProjection(spans=(bad_end,)), transcript
        )


def test_transcript_validation_rejects_unknown_evidence_turn():
    finding = ResearchFinding(
        finding_id="finding_" + "e" * 40,
        framework_identifier="apex-spikes-afce",
        finding_type="strength",
        description="A supported observation.",
        evidence_turns=(2,),
        source_reference=_source("strengths"),
    )
    transcript = (
        ResearchTranscriptTurn(
            turn_number=1,
            role="clinician",
            source_role="user",
            text="Hello.",
        ),
    )
    with pytest.raises(ValueError, match="unknown transcript turn"):
        validate_projection_against_transcript(
            ResearchProjection(findings=(finding,)), transcript
        )
