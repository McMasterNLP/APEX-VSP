"""Lifecycle, policy, history, and concurrency tests for human review."""

from __future__ import annotations

import pytest

from core.time import serialize_utc_datetime, utc_now
from domain.models.evaluator_comparison import EvaluatorRunResult
from domain.models.research_evaluation import (
    ResearchEvaluationEnvelope,
    ResearchEvaluationResponse,
    ResearchEvaluatorMetadata,
    ResearchProvenance,
    ResearchRunMetadata,
)
from domain.entities.research_annotation import ResearchReviewDecisionRevision
from domain.entities.user import User
from domain.models.research_annotation import (
    AnnotationSetCompleteRequest,
    AnnotationSetCreateRequest,
    AnnotationSetReopenRequest,
    AuthoredRelationCreateRequest,
    CanonicalSpanSelection,
    CoverageDeclarationWriteRequest,
    DimensionRatingCorrection,
    HumanAnnotationCreateRequest,
    HumanAnnotationRevisionRequest,
    ResearchEvaluationRunSaveRequest,
    ReviewDecisionWriteRequest,
    SpanCorrection,
    SpanAttributeValue,
)
from schemas.ace_ct import ACECTEvaluationResult
from services.ace_ct_results import (
    build_ace_ct_framework_results,
    project_ace_ct_compatibility_scores,
)
from services.evaluator_comparison_service import build_evaluator_provenance
from services.research_adapters.base import ResearchAdapterContext
from services.research_adapters.defaults import build_default_research_adapter_registry
from services.research_annotation_policy import (
    ACE_GUIDELINE_IDENTIFIER,
    ACE_GUIDELINE_VERSION,
    APEX_GUIDELINE_IDENTIFIER,
    APEX_GUIDELINE_VERSION,
)
from services.research_annotation_service import (
    ResearchAnnotationService,
    ResearchAnnotationServiceError,
)
from services.research_evaluation_run_service import ResearchEvaluationRunService
from tests.services import test_research_evaluation_service as item1_service_tests
from tests.utils.ace_ct import build_valid_ace_ct_payload


@pytest.fixture
def test_db():
    yield from item1_service_tests.test_db.__wrapped__()


@pytest.fixture
def completed_session(test_db):
    return item1_service_tests.completed_session.__wrapped__(test_db)


@pytest.fixture
def reviewers(test_db):
    first = User(email="reviewer-one@example.com", role="admin", full_name="One")
    second = User(email="reviewer-two@example.com", role="admin", full_name="Two")
    test_db.add_all([first, second])
    test_db.commit()
    return first, second


@pytest.fixture
async def annotation_context(test_db, completed_session, reviewers):
    run_service = ResearchEvaluationRunService(
        test_db,
        evaluation_service=item1_service_tests._service(test_db),
    )
    run = await run_service.run_and_save(
        completed_session.id,
        ResearchEvaluationRunSaveRequest(evaluator_identifier="baseline"),
        reviewers[0],
    )
    service = ResearchAnnotationService(test_db, run_service=run_service)
    annotation_set = service.create_annotation_set(
        run.run_uuid,
        AnnotationSetCreateRequest(
            guideline_identifier=APEX_GUIDELINE_IDENTIFIER,
            guideline_version=APEX_GUIDELINE_VERSION,
        ),
        reviewers[0],
    )
    return service, annotation_set, reviewers


async def _ace_annotation_context(test_db, completed_session, reviewer):
    item1_service = item1_service_tests._service(test_db)
    turns, response_identity = item1_service.completed_transcript(completed_session.id)
    envelope_identity = response_identity.model_copy(
        update={"raw_transcript_included": False}
    )
    registration = build_default_research_adapter_registry().get("ace_ct_inspired")
    context = ResearchAdapterContext(
        transcript_hash=envelope_identity.canonical_transcript_hash,
        transcript_turns=turns,
        evaluator_identifier="ace_ct_inspired",
        framework_identifier=registration.framework.identifier,
    )
    evaluation = ACECTEvaluationResult.model_validate(
        build_valid_ace_ct_payload(evidence_turn_numbers=[1, 2])
    )
    compatibility = project_ace_ct_compatibility_scores(
        evaluation, apex_baseline_spikes_completion_score=50
    )
    framework = build_ace_ct_framework_results(
        evaluation, compatibility_projection=compatibility
    )
    evaluator_run = EvaluatorRunResult(
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
    native = registration.adapter.build_native_result(evaluator_run, context)
    projection = registration.adapter.project(native, context)
    timestamp = serialize_utc_datetime(utc_now())
    envelope = ResearchEvaluationEnvelope(
        run=ResearchRunMetadata(
            run_id="run_" + "b" * 40,
            timestamp=timestamp,
            runtime_ms=3,
            execution_mode="live",
            completion_status="success",
        ),
        transcript=envelope_identity,
        evaluator=ResearchEvaluatorMetadata(
            identifier="ace_ct_inspired",
            display_name=registration.display_name,
            version=registration.evaluator_version,
            evaluator_type="experimental_rubric_llm",
            provider="openai",
            model_identifier="synthetic-model",
        ),
        framework=registration.framework,
        adapter=registration.adapter_metadata,
        capabilities=registration.capabilities,
        framework_result=native,
        projection=projection,
        status="success",
        provenance=ResearchProvenance(
            generated_at=timestamp,
            runtime_ms=3,
            live_execution=True,
        ),
    )

    class StubEvaluationService:
        async def evaluate(self, session_id, request):
            return ResearchEvaluationResponse(
                transcript=response_identity,
                transcript_turns=turns,
                results=(envelope,),
            )

        def completed_transcript(self, session_id):
            return turns, response_identity

    run_service = ResearchEvaluationRunService(
        test_db,
        evaluation_service=StubEvaluationService(),
    )
    saved = await run_service.run_and_save(
        completed_session.id,
        ResearchEvaluationRunSaveRequest(
            evaluator_identifier="ace_ct_inspired",
            allow_live=True,
            provider="openai",
        ),
        reviewer,
    )
    service = ResearchAnnotationService(test_db, run_service=run_service)
    annotation_set = service.create_annotation_set(
        saved.run_uuid,
        AnnotationSetCreateRequest(
            guideline_identifier=ACE_GUIDELINE_IDENTIFIER,
            guideline_version=ACE_GUIDELINE_VERSION,
        ),
        reviewer,
    )
    return service, annotation_set


@pytest.mark.asyncio
async def test_create_set_is_reviewer_specific_and_compatible_idempotent(annotation_context):
    service, annotation_set, reviewers = annotation_context
    same = service.create_annotation_set(
        annotation_set.evaluation_run_uuid,
        AnnotationSetCreateRequest(
            guideline_identifier=APEX_GUIDELINE_IDENTIFIER,
            guideline_version=APEX_GUIDELINE_VERSION,
        ),
        reviewers[0],
    )
    other = service.create_annotation_set(
        annotation_set.evaluation_run_uuid,
        AnnotationSetCreateRequest(
            guideline_identifier=APEX_GUIDELINE_IDENTIFIER,
            guideline_version=APEX_GUIDELINE_VERSION,
        ),
        reviewers[1],
    )
    assert same.annotation_set_uuid == annotation_set.annotation_set_uuid
    assert other.annotation_set_uuid != annotation_set.annotation_set_uuid
    assert annotation_set.status == "draft"
    assert annotation_set.progress.total > 0


@pytest.mark.asyncio
async def test_decisions_are_append_only_and_effective_revision_is_latest(annotation_context):
    service, annotation_set, reviewers = annotation_context
    prediction = annotation_set.eligible_predictions[0]
    first = service.record_decision(
        annotation_set.annotation_set_uuid,
        prediction.prediction_id,
        ReviewDecisionWriteRequest(
            expected_set_revision=0,
            decision="confirmed",
            reviewer_note="Initial confirmation.",
        ),
        reviewers[0],
    )
    second = service.record_decision(
        annotation_set.annotation_set_uuid,
        prediction.prediction_id,
        ReviewDecisionWriteRequest(
            expected_set_revision=1,
            expected_decision_revision=1,
            decision="rejected",
            reviewer_note="Reconsidered after context review.",
        ),
        reviewers[0],
    )
    assert first.status == "in_review"
    assert second.revision == 2
    assert [item.decision for item in second.decision_revisions] == [
        "confirmed",
        "rejected",
    ]
    assert second.effective_decisions[0].decision == "rejected"
    assert second.decision_revisions[1].supersedes_uuid == second.decision_revisions[0].decision_uuid
    assert service.db.query(ResearchReviewDecisionRevision).count() == 2


@pytest.mark.asyncio
async def test_stale_revision_conflict_does_not_overwrite(annotation_context):
    service, annotation_set, reviewers = annotation_context
    prediction = annotation_set.eligible_predictions[0]
    service.record_decision(
        annotation_set.annotation_set_uuid,
        prediction.prediction_id,
        ReviewDecisionWriteRequest(expected_set_revision=0, decision="confirmed"),
        reviewers[0],
    )
    with pytest.raises(ResearchAnnotationServiceError) as conflict:
        service.record_decision(
            annotation_set.annotation_set_uuid,
            prediction.prediction_id,
            ReviewDecisionWriteRequest(expected_set_revision=0, decision="rejected"),
            reviewers[0],
        )
    assert conflict.value.category == "revision_conflict"
    assert conflict.value.current_set_revision == 1
    assert service.db.query(ResearchReviewDecisionRevision).count() == 1


@pytest.mark.asyncio
async def test_invalid_label_unknown_prediction_and_wrong_reviewer_are_rejected(
    annotation_context,
):
    service, annotation_set, reviewers = annotation_context
    prediction = next(
        item
        for item in annotation_set.eligible_predictions
        if item.projection_type == "span_annotation"
    )
    with pytest.raises(ResearchAnnotationServiceError) as invalid_label:
        service.record_decision(
            annotation_set.annotation_set_uuid,
            prediction.prediction_id,
            ReviewDecisionWriteRequest(
                expected_set_revision=0,
                decision="corrected",
                correction=SpanCorrection(
                    corrected_label="arbitrary_free_text",
                    corrected_dimension=None,
                ),
            ),
            reviewers[0],
        )
    assert invalid_label.value.category == "invalid_correction"

    with pytest.raises(ResearchAnnotationServiceError) as unknown:
        service.record_decision(
            annotation_set.annotation_set_uuid,
            "span_" + "0" * 40,
            ReviewDecisionWriteRequest(expected_set_revision=0, decision="confirmed"),
            reviewers[0],
        )
    assert unknown.value.category == "invalid_prediction"

    with pytest.raises(ResearchAnnotationServiceError) as forbidden:
        service.record_decision(
            annotation_set.annotation_set_uuid,
            prediction.prediction_id,
            ReviewDecisionWriteRequest(expected_set_revision=0, decision="confirmed"),
            reviewers[1],
        )
    assert forbidden.value.category == "annotation_set_forbidden"


@pytest.mark.asyncio
async def test_rating_score_insufficient_evidence_and_evidence_turn_validation(
    test_db, completed_session, reviewers
):
    service, annotation_set = await _ace_annotation_context(
        test_db, completed_session, reviewers[0]
    )
    rating = next(
        item
        for item in annotation_set.eligible_predictions
        if item.projection_type == "dimension_rating"
    )
    original = rating.original_prediction
    corrected = service.record_decision(
        annotation_set.annotation_set_uuid,
        rating.prediction_id,
        ReviewDecisionWriteRequest(
            expected_set_revision=0,
            decision="corrected",
            correction=DimensionRatingCorrection(
                corrected_score=3,
                corrected_score_status="available",
                corrected_assessability=original.assessability,
                corrected_evidence_turns=(1, 3),
            ),
        ),
        reviewers[0],
    )
    insufficient = service.record_decision(
        annotation_set.annotation_set_uuid,
        rating.prediction_id,
        ReviewDecisionWriteRequest(
            expected_set_revision=1,
            expected_decision_revision=1,
            decision="insufficient_evidence",
            correction=DimensionRatingCorrection(
                corrected_score=None,
                corrected_score_status="insufficient_evidence",
                corrected_assessability=original.assessability,
                corrected_evidence_turns=(2,),
            ),
        ),
        reviewers[0],
    )
    assert corrected.progress.corrected == 1
    assert insufficient.progress.insufficient_evidence == 1

    with pytest.raises(ResearchAnnotationServiceError) as invalid_score:
        service.record_decision(
            annotation_set.annotation_set_uuid,
            rating.prediction_id,
            ReviewDecisionWriteRequest(
                expected_set_revision=2,
                expected_decision_revision=2,
                decision="corrected",
                correction=DimensionRatingCorrection(
                    corrected_score=4.5,
                    corrected_score_status="available",
                    corrected_assessability=original.assessability,
                    corrected_evidence_turns=(1,),
                ),
            ),
            reviewers[0],
        )
    assert invalid_score.value.category == "invalid_correction"

    with pytest.raises(ResearchAnnotationServiceError) as invalid_evidence:
        service.record_decision(
            annotation_set.annotation_set_uuid,
            rating.prediction_id,
            ReviewDecisionWriteRequest(
                expected_set_revision=2,
                expected_decision_revision=2,
                decision="corrected",
                correction=DimensionRatingCorrection(
                    corrected_score=2,
                    corrected_score_status="available",
                    corrected_assessability=original.assessability,
                    corrected_evidence_turns=(999,),
                ),
            ),
            reviewers[0],
        )
    assert invalid_evidence.value.category == "invalid_correction"


@pytest.mark.asyncio
async def test_completion_blocks_unreviewed_then_locks_and_reopen_audits(annotation_context):
    service, annotation_set, reviewers = annotation_context
    with pytest.raises(ResearchAnnotationServiceError) as incomplete:
        service.complete(
            annotation_set.annotation_set_uuid,
            AnnotationSetCompleteRequest(expected_set_revision=0),
            reviewers[0],
        )
    assert incomplete.value.category == "completion_blocked"

    current = annotation_set
    for prediction in annotation_set.eligible_predictions:
        current = service.record_decision(
            annotation_set.annotation_set_uuid,
            prediction.prediction_id,
            ReviewDecisionWriteRequest(
                expected_set_revision=current.revision,
                decision="confirmed",
            ),
            reviewers[0],
        )
    complete = service.complete(
        annotation_set.annotation_set_uuid,
        AnnotationSetCompleteRequest(expected_set_revision=current.revision),
        reviewers[0],
    )
    assert complete.status == "complete"
    assert complete.locked is True
    with pytest.raises(ResearchAnnotationServiceError) as locked:
        service.record_decision(
            annotation_set.annotation_set_uuid,
            annotation_set.eligible_predictions[0].prediction_id,
            ReviewDecisionWriteRequest(
                expected_set_revision=complete.revision,
                expected_decision_revision=1,
                decision="rejected",
            ),
            reviewers[0],
        )
    assert locked.value.category == "annotation_set_locked"

    reopened = service.reopen(
        annotation_set.annotation_set_uuid,
        AnnotationSetReopenRequest(
            expected_set_revision=complete.revision,
            reason="Expert requested a documented second pass.",
        ),
        reviewers[1],
    )
    assert reopened.status == "in_review"
    assert reopened.locked is False
    assert [event.to_status for event in reopened.transitions] == [
        "complete",
        "in_review",
    ]
    assert reopened.transitions[-1].reason.startswith("Expert requested")
    assert len(reopened.decision_revisions) == len(annotation_set.eligible_predictions)


@pytest.mark.asyncio
async def test_completion_rejects_relation_with_rejected_endpoint(annotation_context):
    service, annotation_set, reviewers = annotation_context
    relation = next(
        item
        for item in annotation_set.eligible_predictions
        if item.projection_type == "relation"
    )
    rejected_endpoint = relation.original_prediction.source_annotation_id
    current = annotation_set
    for prediction in annotation_set.eligible_predictions:
        current = service.record_decision(
            annotation_set.annotation_set_uuid,
            prediction.prediction_id,
            ReviewDecisionWriteRequest(
                expected_set_revision=current.revision,
                decision=(
                    "rejected"
                    if prediction.prediction_id == rejected_endpoint
                    else "confirmed"
                ),
            ),
            reviewers[0],
        )

    assert current.progress.unreviewed == 0
    with pytest.raises(ResearchAnnotationServiceError) as incoherent:
        service.complete(
            annotation_set.annotation_set_uuid,
            AnnotationSetCompleteRequest(expected_set_revision=current.revision),
            reviewers[0],
        )
    assert incoherent.value.category == "completion_blocked"
    assert "rejected endpoint" in str(incoherent.value).lower()


@pytest.mark.asyncio
async def test_human_span_unicode_overlap_lifecycle_relation_and_coverage(annotation_context):
    service, annotation_set, reviewers = annotation_context
    run = service.run_service.get_run(annotation_set.evaluation_run_uuid)
    turn = run.transcript_snapshot[0]
    text = turn.text[: max(1, min(8, len(turn.text)))]

    def selection(selected=text):
        return CanonicalSpanSelection(
            transcript_hash=annotation_set.transcript_hash,
            start_turn_number=turn.turn_number,
            end_turn_number=turn.turn_number,
            speaker=turn.role,
            start_offset=0,
            end_offset=len(selected),
            selected_text=selected,
        )

    current = service.create_human_annotation(
        annotation_set.annotation_set_uuid,
        HumanAnnotationCreateRequest(
            expected_set_revision=0,
            selection=selection(),
            label="empathic_opportunity",
            dimension="Feeling",
            attributes=(SpanAttributeValue(identifier="explicit_or_implicit", value="explicit"),),
        ),
        reviewers[0],
    )
    source = current.active_human_annotations[0]
    current = service.create_human_annotation(
        annotation_set.annotation_set_uuid,
        HumanAnnotationCreateRequest(
            expected_set_revision=current.revision,
            selection=selection(),
            label="empathic_response",
        ),
        reviewers[0],
    )
    target = next(item for item in current.active_human_annotations if item.annotation_id != source.annotation_id)
    assert len(current.active_human_annotations) == 2  # overlapping spans stay distinct

    current = service.create_authored_relation(
        annotation_set.annotation_set_uuid,
        AuthoredRelationCreateRequest(
            expected_set_revision=current.revision,
            source_annotation_id=source.annotation_id,
            target_annotation_id=target.annotation_id,
            relation_type="responds_to",
        ),
        reviewers[0],
    )
    assert current.active_authored_relations[0].source_annotation_id == source.annotation_id
    current = service.revise_human_annotation(
        annotation_set.annotation_set_uuid,
        target.annotation_id,
        HumanAnnotationRevisionRequest(
            expected_set_revision=current.revision,
            expected_annotation_revision=1,
            operation="retire",
        ),
        reviewers[0],
    )
    assert target.annotation_id not in {item.annotation_id for item in current.active_human_annotations}
    current = service.revise_human_annotation(
        annotation_set.annotation_set_uuid,
        target.annotation_id,
        HumanAnnotationRevisionRequest(
            expected_set_revision=current.revision,
            expected_annotation_revision=2,
            operation="restore",
        ),
        reviewers[0],
    )
    current = service.declare_coverage(
        annotation_set.annotation_set_uuid,
        CoverageDeclarationWriteRequest(
            expected_set_revision=current.revision,
            coverage="not_assessed",
        ),
        reviewers[0],
    )
    assert current.coverage_level == "not_assessed"
    assert "span_precision" in current.validation_eligibility.ineligible_metric_identifiers
    assert "span_recall" in current.validation_eligibility.ineligible_metric_identifiers
    assert any(item.provenance.method == "human_annotation" for item in current.resolved_projection.spans)


@pytest.mark.asyncio
async def test_server_rejects_stale_text_and_resolves_model_boundary_correction(annotation_context):
    service, annotation_set, reviewers = annotation_context
    run = service.run_service.get_run(annotation_set.evaluation_run_uuid)
    turn = run.transcript_snapshot[0]
    with pytest.raises(ResearchAnnotationServiceError) as stale:
        service.create_human_annotation(
            annotation_set.annotation_set_uuid,
            HumanAnnotationCreateRequest(
                expected_set_revision=0,
                selection=CanonicalSpanSelection(
                    transcript_hash="0" * 64,
                    start_turn_number=turn.turn_number,
                    end_turn_number=turn.turn_number,
                    speaker=turn.role,
                    start_offset=0,
                    end_offset=1,
                    selected_text=turn.text[:1],
                ),
                label="elicitation",
            ),
            reviewers[0],
        )
    assert stale.value.category == "invalid_selection"

    prediction = next(
        item for item in annotation_set.eligible_predictions
        if item.projection_type == "span_annotation"
    )
    original = prediction.original_prediction
    source_turn = next(item for item in run.transcript_snapshot if item.turn_number == original.turn_number)
    start = original.start_offset
    end = original.end_offset
    if end < len(source_turn.text):
        end += 1
    else:
        start -= 1
    selected = source_turn.text[start:end]
    corrected = service.record_decision(
        annotation_set.annotation_set_uuid,
        prediction.prediction_id,
        ReviewDecisionWriteRequest(
            expected_set_revision=0,
            decision="corrected",
            correction=SpanCorrection(
                corrected_label=original.label,
                corrected_dimension=original.dimension,
                corrected_start_char=start,
                corrected_end_char=end,
                corrected_text=selected,
                transcript_hash=annotation_set.transcript_hash,
                corrected_turn_number=original.turn_number,
                corrected_speaker=source_turn.role,
            ),
        ),
        reviewers[0],
    )
    resolved = next(item for item in corrected.resolved_projection.spans if item.prediction_id == prediction.prediction_id)
    assert resolved.quoted_text == selected
    assert resolved.provenance.method == "human_correction"
    assert prediction.original_prediction.quoted_text == original.quoted_text


@pytest.mark.asyncio
async def test_assessed_coverage_requires_fixed_inventory_review(annotation_context):
    service, annotation_set, reviewers = annotation_context
    with pytest.raises(ResearchAnnotationServiceError) as blocked:
        service.declare_coverage(
            annotation_set.annotation_set_uuid,
            CoverageDeclarationWriteRequest(
                expected_set_revision=0, coverage="prediction_review_only"
            ),
            reviewers[0],
        )
    assert blocked.value.category == "invalid_coverage"
    current = annotation_set
    for prediction in annotation_set.eligible_predictions:
        current = service.record_decision(
            annotation_set.annotation_set_uuid,
            prediction.prediction_id,
            ReviewDecisionWriteRequest(
                expected_set_revision=current.revision, decision="confirmed"
            ),
            reviewers[0],
        )
    current = service.declare_coverage(
        annotation_set.annotation_set_uuid,
        CoverageDeclarationWriteRequest(
            expected_set_revision=current.revision,
            coverage="prediction_review_only",
        ),
        reviewers[0],
    )
    assert "span_precision" in current.validation_eligibility.eligible_metric_identifiers
    assert "span_recall" in current.validation_eligibility.ineligible_metric_identifiers
