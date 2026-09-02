"""Persistence and immutability tests for server-generated research runs."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from domain.entities.research_annotation import ResearchEvaluationRun
from domain.entities.user import User
from domain.models.research_annotation import ResearchEvaluationRunSaveRequest
from services.research_evaluation_run_service import (
    ResearchEvaluationRunService,
    ResearchEvaluationRunServiceError,
)
from tests.services import test_research_evaluation_service as item1_service_tests


@pytest.fixture
def test_db():
    yield from item1_service_tests.test_db.__wrapped__()


@pytest.fixture
def completed_session(test_db):
    return item1_service_tests.completed_session.__wrapped__(test_db)


@pytest.fixture
def admin_reviewer(test_db) -> User:
    user = User(email="annotation-admin@example.com", role="admin", full_name="Reviewer")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_run_and_save_persists_exact_server_envelope_and_snapshot_only(
    test_db, completed_session, admin_reviewer
):
    before = item1_service_tests._database_snapshot(test_db, completed_session.id)
    service = ResearchEvaluationRunService(
        test_db,
        evaluation_service=item1_service_tests._service(test_db),
    )
    record = await service.run_and_save(
        completed_session.id,
        ResearchEvaluationRunSaveRequest(evaluator_identifier="baseline"),
        admin_reviewer,
    )
    after = item1_service_tests._database_snapshot(test_db, completed_session.id)

    assert before == after
    assert record.envelope.status == "success"
    assert record.run_uuid.hex not in record.envelope.run.run_id
    stored = test_db.scalar(
        select(ResearchEvaluationRun).where(ResearchEvaluationRun.id == record.run_uuid)
    )
    assert stored is not None
    assert json.loads(stored.envelope_json) == record.envelope.model_dump(mode="json")
    assert json.loads(stored.transcript_snapshot_json) == [
        turn.model_dump(mode="json") for turn in record.transcript_snapshot
    ]
    assert "annotation-admin@example.com" not in stored.envelope_json
    assert "annotation-admin@example.com" not in stored.transcript_snapshot_json


@pytest.mark.asyncio
async def test_failed_or_refused_run_is_not_persisted(
    test_db, completed_session, admin_reviewer
):
    service = ResearchEvaluationRunService(
        test_db,
        evaluation_service=item1_service_tests._service(test_db),
    )
    with pytest.raises(ResearchEvaluationRunServiceError) as refused:
        await service.run_and_save(
            completed_session.id,
            ResearchEvaluationRunSaveRequest(evaluator_identifier="hybrid_v1"),
            admin_reviewer,
        )
    assert refused.value.category == "live_execution_refused"
    assert test_db.query(ResearchEvaluationRun).count() == 0


@pytest.mark.asyncio
async def test_saved_run_detects_current_transcript_mismatch(
    test_db, completed_session, admin_reviewer
):
    service = ResearchEvaluationRunService(
        test_db,
        evaluation_service=item1_service_tests._service(test_db),
    )
    saved = await service.run_and_save(
        completed_session.id,
        ResearchEvaluationRunSaveRequest(evaluator_identifier="baseline"),
        admin_reviewer,
    )
    completed_session.turns[0].text = "Changed after the research snapshot."
    test_db.commit()
    retrieved = service.get_run(saved.run_uuid)
    assert retrieved.transcript_matches_current is False
    assert retrieved.current_transcript_hash != retrieved.envelope.transcript.canonical_transcript_hash


@pytest.mark.asyncio
async def test_saved_run_entity_rejects_update_and_delete(
    test_db, completed_session, admin_reviewer
):
    service = ResearchEvaluationRunService(
        test_db,
        evaluation_service=item1_service_tests._service(test_db),
    )
    saved = await service.run_and_save(
        completed_session.id,
        ResearchEvaluationRunSaveRequest(evaluator_identifier="baseline"),
        admin_reviewer,
    )
    entity = test_db.get(ResearchEvaluationRun, saved.run_uuid)
    entity.envelope_json = "{}"
    with pytest.raises(ValueError, match="Immutable"):
        test_db.commit()
    test_db.rollback()

    entity = test_db.get(ResearchEvaluationRun, saved.run_uuid)
    test_db.delete(entity)
    with pytest.raises(ValueError, match="Immutable"):
        test_db.commit()
    test_db.rollback()
