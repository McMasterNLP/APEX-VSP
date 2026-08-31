"""Tests for isolated, non-persisting evaluator orchestration."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from domain.entities.case import Case
from domain.entities.feedback import Feedback
from domain.entities.session import Session as SessionEntity
from domain.entities.turn import Turn
from domain.entities.user import User
from services.evaluator_comparison_service import EvaluatorComparisonService
from services.scoring_service import ScoringService
from tests.utils.ace_ct import FakeACECTAdapter
from tests.utils.transcript_runner import create_all_for_test_engine


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    create_all_for_test_engine(engine)
    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def stored_session(test_db) -> SessionEntity:
    user = User(email="runner@example.com", role="trainee", full_name="Runner User")
    case = Case(
        title="Runner case",
        description="d",
        script="s",
        difficulty_level="intermediate",
        category="test",
        patient_background="pb",
        expected_spikes_flow=None,
    )
    test_db.add_all([user, case])
    test_db.commit()

    session = SessionEntity(
        user_id=user.id,
        case_id=case.id,
        state="completed",
        current_spikes_stage="strategy",
        started_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
        ended_at=datetime(2026, 2, 1, 10, 5, tzinfo=UTC),
        duration_seconds=300,
        session_metadata='{"private":"unchanged"}',
        evaluator_plugin="plugins.evaluators.apex_baseline_evaluator:ApexBaselineEvaluator",
        evaluator_version="1.0",
        patient_model_plugin="patient.test",
        patient_model_version="3.0",
        metrics_plugins='["metric.test"]',
        metrics_json='{"existing":true}',
    )
    test_db.add(session)
    test_db.commit()

    turns = [
        Turn(
            session_id=session.id,
            user_id=user.id,
            turn_number=1,
            role="user",
            text="How are you feeling?",
            metrics_json='{"question_type":"open","tone":{"clear":true,"calm":true}}',
            spans_json="[]",
            spikes_stage="perception",
            timestamp=datetime(2026, 2, 1, 10, 1, tzinfo=UTC),
        ),
        Turn(
            session_id=session.id,
            turn_number=2,
            role="assistant",
            text="I am scared.",
            spans_json=json.dumps(
                [
                    {
                        "span_type": "eo",
                        "dimension": "Feeling",
                        "explicit_or_implicit": "explicit",
                    }
                ]
            ),
            spikes_stage="emotion",
            timestamp=datetime(2026, 2, 1, 10, 2, tzinfo=UTC),
        ),
        Turn(
            session_id=session.id,
            user_id=user.id,
            turn_number=3,
            role="user",
            text="I understand that this is scary.",
            metrics_json='{"tone":{"clear":true,"calm":true}}',
            spans_json=json.dumps([{"span_type": "response", "type": "understanding"}]),
            spikes_stage="strategy",
            timestamp=datetime(2026, 2, 1, 10, 3, tzinfo=UTC),
        ),
    ]
    test_db.add_all(turns)
    test_db.add(
        Feedback(
            session_id=session.id,
            empathy_score=11.0,
            communication_score=22.0,
            spikes_completion_score=33.0,
            overall_score=44.0,
            strengths="Existing review",
            evaluator_meta='{"source":"existing"}',
            created_at=datetime(2026, 2, 2, 10, 0, tzinfo=UTC),
        )
    )
    test_db.commit()
    test_db.refresh(session)
    return session


def _table_rows(test_db, entity: Any, where: Any | None = None) -> list[dict[str, Any]]:
    statement = select(entity.__table__)
    if where is not None:
        statement = statement.where(where)
    return [dict(row) for row in test_db.execute(statement).mappings()]


def _database_snapshot(test_db, session_id: int) -> dict[str, list[dict[str, Any]]]:
    session = test_db.get(SessionEntity, session_id)
    assert session is not None
    return {
        "users": _table_rows(test_db, User, User.id == session.user_id),
        "cases": _table_rows(test_db, Case, Case.id == session.case_id),
        "sessions": _table_rows(test_db, SessionEntity, SessionEntity.id == session_id),
        "turns": _table_rows(test_db, Turn, Turn.session_id == session_id),
        "feedback": _table_rows(test_db, Feedback, Feedback.session_id == session_id),
    }


def _patch_hybrid_merges(
    monkeypatch,
    *,
    fail_v1: bool = False,
    fail_v2: bool = False,
) -> None:
    async def fake_v1(self, state, session_id):
        if fail_v1:
            raise RuntimeError("private-token-must-not-escape")
        return (
            71.0,
            72.0,
            73.0,
            72.0,
            {
                "phase": "hybrid_llm_v1",
                "status": "completed",
                "llm_output": {
                    "spikes_annotations": [{"stage": "emotion", "confidence": 0.9}],
                    "stage_turn_mapping": [{"turn_number": 2, "stage": "emotion"}],
                },
            },
        )

    async def fake_v2(self, state, session_id):
        if fail_v2:
            return (
                state.empathy_score,
                state.communication_score,
                state.spikes_score,
                state.overall_score,
                {"phase": "hybrid_llm_v2", "status": "failed", "error": "raw-private"},
            )
        return (
            81.0,
            82.0,
            83.0,
            82.0,
            {
                "phase": "hybrid_llm_v2",
                "status": "completed",
                "llm_output": {
                    "spikes_annotations": [{"stage": "emotion", "confidence": 0.9}],
                    "stage_turn_mapping": [{"turn_number": 2, "stage": "emotion"}],
                },
            },
        )

    monkeypatch.setattr(ScoringService, "_hybrid_llm_merge_scores", fake_v1)
    monkeypatch.setattr(ScoringService, "_hybrid_v2_llm_merge_scores", fake_v2)


@pytest.mark.asyncio
async def test_all_three_evaluators_succeed_independently(
    test_db, stored_session, monkeypatch
) -> None:
    _patch_hybrid_merges(monkeypatch)

    results = await EvaluatorComparisonService(test_db, model_identifier="gpt-test").run_evaluators(
        stored_session.id
    )

    assert [result.evaluator_identifier for result in results] == [
        "baseline",
        "hybrid_v1",
        "hybrid_v2",
    ]
    assert all(result.status == "success" for result in results)
    assert len({result.transcript_hash for result in results}) == 1
    assert all(result.runtime_ms >= 0 for result in results)
    assert [result.evaluator_name for result in results] == [
        "ApexBaselineEvaluator",
        "ApexHybridEvaluator",
        "ApexHybridV2Evaluator",
    ]
    assert [result.evaluator_version for result in results] == ["1.0", "1.0", "2.0"]
    assert all(result.structured_feedback is not None for result in results)


@pytest.mark.parametrize(
    ("fail_v1", "fail_v2", "expected_statuses"),
    [
        (True, False, ["success", "failed", "success"]),
        (False, True, ["success", "success", "failed"]),
        (True, True, ["success", "failed", "failed"]),
    ],
)
@pytest.mark.asyncio
async def test_hybrid_failures_do_not_discard_other_results(
    test_db,
    stored_session,
    monkeypatch,
    fail_v1,
    fail_v2,
    expected_statuses,
) -> None:
    _patch_hybrid_merges(monkeypatch, fail_v1=fail_v1, fail_v2=fail_v2)

    results = await EvaluatorComparisonService(test_db).run_evaluators(stored_session.id)

    assert [result.status for result in results] == expected_statuses
    for result in results:
        if result.status == "failed":
            assert result.scores is None
            assert result.structured_feedback is None
            assert result.error is not None
            serialized = result.model_dump_json()
            assert "private-token" not in serialized
            assert "raw-private" not in serialized


@pytest.mark.asyncio
async def test_unknown_evaluator_is_rejected(test_db, stored_session) -> None:
    with pytest.raises(ValueError, match="Unknown evaluator identifier"):
        await EvaluatorComparisonService(test_db).run_evaluators(
            stored_session.id, ["baseline", "not_registered"]
        )


@pytest.mark.asyncio
async def test_runner_leaves_all_stored_rows_unchanged(
    test_db, stored_session, monkeypatch
) -> None:
    _patch_hybrid_merges(monkeypatch)
    before = _database_snapshot(test_db, stored_session.id)

    await EvaluatorComparisonService(test_db).run_evaluators(stored_session.id)

    after = _database_snapshot(test_db, stored_session.id)
    assert after == before
    assert len(after["feedback"]) == 1
    assert len(after["turns"]) == 3
    assert after["sessions"][0]["metrics_json"] == '{"existing":true}'


@pytest.mark.asyncio
async def test_existing_production_baseline_persistence_still_works(
    test_db, stored_session
) -> None:
    response = await ScoringService(test_db).generate_feedback_rule_only(stored_session.id)
    stored = test_db.query(Feedback).filter_by(session_id=stored_session.id).one()

    assert response.session_id == stored_session.id
    assert stored.overall_score == response.overall_score
    assert json.loads(stored.evaluator_meta)["phase"] == "baseline_rule_v1"


@pytest.mark.asyncio
async def test_ace_ct_comparison_reuses_transcript_without_persistence(
    test_db, stored_session
) -> None:
    before = _database_snapshot(test_db, stored_session.id)

    results = await EvaluatorComparisonService(
        test_db,
        llm_provider="gemini",
        model_identifier="synthetic-fake-model",
        llm_adapter=FakeACECTAdapter(),
        allow_experimental_override=True,
    ).run_evaluators(stored_session.id, ["baseline", "ace_ct_inspired"])

    after = _database_snapshot(test_db, stored_session.id)
    assert after == before
    assert [result.status for result in results] == ["success", "success"]
    assert len({result.transcript_hash for result in results}) == 1
    assert results[1].provenance.llm_provider == "gemini"
    assert results[1].provenance.model_identifier == "synthetic-fake-model"
    assert results[1].framework_results is not None
    assert len(results[1].framework_results.dimension_results) == 11
    assert results[1].structured_feedback is not None


@pytest.mark.asyncio
async def test_ace_ct_failure_preserves_successful_baseline(test_db, stored_session) -> None:
    before = _database_snapshot(test_db, stored_session.id)

    results = await EvaluatorComparisonService(
        test_db,
        llm_provider="openai",
        model_identifier="synthetic-fake-model",
        llm_adapter=FakeACECTAdapter(raw_response="not-json"),
        allow_experimental_override=True,
    ).run_evaluators(stored_session.id, ["baseline", "ace_ct_inspired"])

    assert _database_snapshot(test_db, stored_session.id) == before
    assert [result.status for result in results] == ["success", "failed"]
    assert results[0].structured_feedback is not None
    assert results[1].structured_feedback is None
    assert results[1].framework_results is None
    assert results[1].error is not None
    assert "not-json" not in results[1].model_dump_json()
