"""Regression tests for deterministic, non-persisting baseline scoring."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from domain.entities.case import Case
from domain.entities.feedback import Feedback
from domain.entities.session import Session as SessionEntity
from domain.entities.turn import Turn
from domain.entities.user import User
from domain.models.scoring import ComputedFeedback
from services.scoring_service import ScoringService
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
def completed_session(test_db) -> SessionEntity:
    user = User(
        email="memory-only-scoring@example.com",
        role="trainee",
        full_name="Memory Only Scoring",
    )
    case = Case(
        title="Memory-only scoring case",
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
        current_spikes_stage="emotion",
        started_at=datetime(2026, 1, 2, 12, 0, tzinfo=UTC),
        ended_at=datetime(2026, 1, 2, 12, 5, tzinfo=UTC),
        duration_seconds=300,
        session_metadata='{"cohort":"test"}',
        evaluator_plugin="plugins.evaluators.apex_baseline_evaluator:ApexBaselineEvaluator",
        evaluator_version="1.0",
        patient_model_plugin="test.patient",
        patient_model_version="2.0",
        metrics_plugins='["test.metric"]',
        metrics_json='{"already":"present"}',
    )
    test_db.add(session)
    test_db.commit()

    test_db.add_all(
        [
            Turn(
                session_id=session.id,
                user_id=user.id,
                turn_number=1,
                role="user",
                text="How are you feeling about this?",
                metrics_json='{"question_type":"open","tone":{"calm":true,"clear":true}}',
                spans_json=json.dumps(
                    [
                        {
                            "span_type": "elicitation",
                            "type": "direct",
                            "dimension": "Feeling",
                        }
                    ]
                ),
                relations_json='{"untouched":true}',
                spikes_stage="perception",
                timestamp=datetime(2026, 1, 2, 12, 1, tzinfo=UTC),
            ),
            Turn(
                session_id=session.id,
                turn_number=2,
                role="assistant",
                text="I am frightened.",
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
                timestamp=datetime(2026, 1, 2, 12, 2, tzinfo=UTC),
            ),
            Turn(
                session_id=session.id,
                user_id=user.id,
                turn_number=3,
                role="user",
                text="I understand this is frightening.",
                metrics_json='{"tone":{"calm":true,"clear":true}}',
                spans_json=json.dumps([{"span_type": "response", "type": "understanding"}]),
                spikes_stage="strategy",
                timestamp=datetime(2026, 1, 2, 12, 3, tzinfo=UTC),
            ),
        ]
    )
    test_db.commit()
    test_db.refresh(session)
    return session


def _session_snapshot(test_db, session_id: int) -> dict:
    return dict(
        test_db.execute(select(SessionEntity.__table__).where(SessionEntity.id == session_id))
        .mappings()
        .one()
    )


def _turn_snapshots(test_db, session_id: int) -> list[dict]:
    return [
        dict(row)
        for row in test_db.execute(
            select(Turn.__table__).where(Turn.session_id == session_id).order_by(Turn.turn_number)
        ).mappings()
    ]


@pytest.mark.asyncio
async def test_compute_baseline_feedback_is_deterministic_and_does_not_persist(
    test_db, completed_session
):
    session_before = _session_snapshot(test_db, completed_session.id)
    turns_before = _turn_snapshots(test_db, completed_session.id)

    service = ScoringService(test_db)
    first = await service.compute_baseline_feedback(completed_session.id)
    second = await service.compute_baseline_feedback(completed_session.id)

    assert isinstance(first, ComputedFeedback)
    assert first == second
    assert test_db.query(Feedback).filter_by(session_id=completed_session.id).count() == 0
    assert _session_snapshot(test_db, completed_session.id) == session_before
    assert _turn_snapshots(test_db, completed_session.id) == turns_before


@pytest.mark.asyncio
async def test_compute_baseline_feedback_leaves_existing_feedback_unchanged(
    test_db, completed_session
):
    existing = Feedback(
        session_id=completed_session.id,
        empathy_score=12.5,
        communication_score=23.5,
        spikes_completion_score=34.5,
        overall_score=45.5,
        strengths="Curated feedback must remain unchanged",
        evaluator_meta='{"source":"human-review"}',
        created_at=datetime(2026, 1, 3, 9, 0, tzinfo=UTC),
    )
    test_db.add(existing)
    test_db.commit()
    before = dict(
        test_db.execute(select(Feedback.__table__).where(Feedback.id == existing.id))
        .mappings()
        .one()
    )

    await ScoringService(test_db).compute_baseline_feedback(completed_session.id)

    after = dict(
        test_db.execute(select(Feedback.__table__).where(Feedback.id == existing.id))
        .mappings()
        .one()
    )
    assert after == before
    assert test_db.query(Feedback).filter_by(session_id=completed_session.id).count() == 1
