"""Resolved projection and privacy-aware annotation export tests."""

from __future__ import annotations

import json

import pytest

from domain.entities.user import User
from domain.models.research_annotation import (
    AnnotationExportRequest,
    AnnotationSetCreateRequest,
    ResearchEvaluationRunSaveRequest,
    ReviewDecisionWriteRequest,
    SpanCorrection,
)
from services.research_annotation_export_service import ResearchAnnotationExportService
from services.research_annotation_policy import (
    APEX_GUIDELINE_IDENTIFIER,
    APEX_GUIDELINE_VERSION,
)
from services.research_annotation_service import ResearchAnnotationService
from services.research_evaluation_run_service import ResearchEvaluationRunService
from tests.services import test_research_evaluation_service as item1_service_tests


@pytest.fixture
def test_db():
    yield from item1_service_tests.test_db.__wrapped__()


@pytest.fixture
def completed_session(test_db):
    return item1_service_tests.completed_session.__wrapped__(test_db)


@pytest.fixture
async def reviewed_context(test_db, completed_session):
    reviewer = User(
        email="private-reviewer@example.com",
        role="admin",
        full_name="Private Reviewer",
    )
    test_db.add(reviewer)
    test_db.commit()
    run_service = ResearchEvaluationRunService(
        test_db,
        evaluation_service=item1_service_tests._service(test_db),
    )
    run = await run_service.run_and_save(
        completed_session.id,
        ResearchEvaluationRunSaveRequest(evaluator_identifier="baseline"),
        reviewer,
    )
    annotation_service = ResearchAnnotationService(test_db, run_service=run_service)
    annotation_set = annotation_service.create_annotation_set(
        run.run_uuid,
        AnnotationSetCreateRequest(
            guideline_identifier=APEX_GUIDELINE_IDENTIFIER,
            guideline_version=APEX_GUIDELINE_VERSION,
        ),
        reviewer,
    )
    spans = [
        item
        for item in annotation_set.eligible_predictions
        if item.projection_type == "span_annotation"
    ]
    original_first = spans[0].original_prediction
    current = annotation_service.record_decision(
        annotation_set.annotation_set_uuid,
        spans[0].prediction_id,
        ReviewDecisionWriteRequest(
            expected_set_revision=0,
            decision="confirmed",
            reviewer_note="Contact private-reviewer@example.com for adjudication.",
        ),
        reviewer,
    )
    current = annotation_service.record_decision(
        annotation_set.annotation_set_uuid,
        spans[1].prediction_id,
        ReviewDecisionWriteRequest(
            expected_set_revision=current.revision,
            decision="corrected",
            correction=SpanCorrection(
                corrected_label="empathic_opportunity",
                corrected_dimension="Judgment",
            ),
        ),
        reviewer,
    )
    current = annotation_service.record_decision(
        annotation_set.annotation_set_uuid,
        spans[2].prediction_id,
        ReviewDecisionWriteRequest(
            expected_set_revision=current.revision,
            decision="rejected",
        ),
        reviewer,
    )
    export_service = ResearchAnnotationExportService(
        annotation_service, run_service
    )
    return (
        reviewer,
        run,
        annotation_service,
        current,
        export_service,
        spans,
        original_first,
    )


@pytest.mark.asyncio
async def test_resolved_projection_confirms_corrects_and_excludes_without_mutation(
    reviewed_context,
):
    _, _, _, annotation_set, _, spans, original_first = reviewed_context
    resolved = annotation_set.resolved_projection
    assert {item.prediction_id for item in resolved.spans} == {
        spans[0].prediction_id,
        spans[1].prediction_id,
    }
    assert resolved.spans[0] == original_first
    corrected = next(item for item in resolved.spans if item.prediction_id == spans[1].prediction_id)
    assert corrected.label == "empathic_opportunity"
    assert corrected.dimension == "Judgment"
    assert spans[1].original_prediction.label != corrected.label
    assert spans[2].prediction_id not in {item.prediction_id for item in resolved.spans}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "profile", ["full_review", "resolved_projection", "audit_history"]
)
async def test_default_annotation_exports_are_sanitized_and_pseudonymous(
    profile, reviewed_context
):
    reviewer, _, _, annotation_set, export_service, _, _ = reviewed_context
    artifact = export_service.render(
        annotation_set.annotation_set_uuid,
        AnnotationExportRequest(profile=profile),
    )
    payload = json.loads(artifact.content)
    serialized = artifact.content.decode("utf-8")
    assert artifact.media_type == "application/json"
    assert payload["profile"] == profile
    assert payload["raw_transcript_included"] is False
    assert "human-reviewed prediction set" in payload["scientific_limitation"]
    assert reviewer.email not in serialized
    assert reviewer.full_name not in serialized
    assert "[EMAIL_REDACTED]" in serialized
    assert "How are you feeling?" not in serialized
    assert "I feel worried." not in serialized
    assert payload["annotation_set"]["reviewer_reference"].startswith("reviewer_")
    assert "source_session_id" not in serialized


@pytest.mark.asyncio
async def test_full_audit_keeps_revisions_and_resolved_export_excludes_rejection(
    reviewed_context,
):
    _, _, _, annotation_set, export_service, spans, _ = reviewed_context
    audit = json.loads(
        export_service.render(
            annotation_set.annotation_set_uuid,
            AnnotationExportRequest(profile="audit_history"),
        ).content
    )
    resolved = json.loads(
        export_service.render(
            annotation_set.annotation_set_uuid,
            AnnotationExportRequest(profile="resolved_projection"),
        ).content
    )
    assert len(audit["decision_revisions"]) == 3
    assert any(item["decision"] == "rejected" for item in audit["decision_revisions"])
    resolved_ids = {item["prediction_id"] for item in resolved["resolved_projection"]["spans"]}
    assert spans[2].prediction_id not in resolved_ids


@pytest.mark.asyncio
async def test_transcript_inclusive_export_is_explicit_and_warned(reviewed_context):
    reviewer, _, _, annotation_set, export_service, _, _ = reviewed_context
    payload = json.loads(
        export_service.render(
            annotation_set.annotation_set_uuid,
            AnnotationExportRequest(
                profile="full_review",
                include_transcript_content=True,
            ),
        ).content
    )
    assert payload["raw_transcript_included"] is True
    assert payload["transcript_snapshot"][0]["text"] == "How are you feeling?"
    assert "exact transcript text" in payload["sensitive_data_warning"]
    assert reviewer.email not in json.dumps(payload)
