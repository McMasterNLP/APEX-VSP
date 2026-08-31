"""Plugin and persistence tests for the experimental ACE-CT-inspired evaluator."""

from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import pytest

from config.settings import Settings
from domain.entities.case import Case
from domain.entities.feedback import Feedback
from domain.entities.session import Session as SessionEntity
from domain.entities.turn import Turn
from domain.entities.user import User
from plugins.evaluators.ace_ct_inspired_evaluator import ACECTInspiredRubricEvaluator
from plugins.registry import PluginRegistry
from services.ace_ct_computation_service import (
    ACECTComputationError,
    compute_ace_ct_evaluation,
)
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
    user = User(email="synthetic@example.invalid", role="trainee", full_name="Synthetic User")
    case = Case(
        title="Synthetic ACE-CT case",
        description="Synthetic test case",
        script="Synthetic script",
        difficulty_level="intermediate",
        category="test",
        patient_background="Synthetic background",
        expected_spikes_flow=None,
    )
    test_db.add_all([user, case])
    test_db.commit()
    session = SessionEntity(
        user_id=user.id,
        case_id=case.id,
        state="completed",
        evaluator_plugin=ACECTInspiredRubricEvaluator.name,
        evaluator_version=ACECTInspiredRubricEvaluator.version,
        patient_model_plugin="fixture-only",
        patient_model_version="1.0",
        metrics_plugins="[]",
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
                text="What matters most to you?",
                spikes_stage="perception",
            ),
            Turn(
                session_id=session.id,
                turn_number=2,
                role="assistant",
                text="I am worried about my family.",
                spikes_stage="emotion",
            ),
        ]
    )
    test_db.commit()
    test_db.refresh(session)
    return session


def _snapshot(test_db) -> dict:
    def rows(entity):
        return [dict(row) for row in test_db.execute(select(entity.__table__)).mappings()]

    return {
        "sessions": rows(SessionEntity),
        "turns": rows(Turn),
        "feedback": rows(Feedback),
    }


def test_registry_discovers_experimental_plugin_metadata() -> None:
    plugin = PluginRegistry.get_evaluator(ACECTInspiredRubricEvaluator.name)

    assert plugin is ACECTInspiredRubricEvaluator
    assert plugin.version == "0.1.0-experimental"
    assert plugin.framework == "ACE-CT-inspired"
    assert plugin.validation_status == "experimental_unvalidated"
    assert plugin.publication_reproduction is False


def test_plugin_is_not_the_default_evaluator() -> None:
    assert Settings.model_fields["evaluator_plugin"].default != ACECTInspiredRubricEvaluator.name


@pytest.mark.asyncio
async def test_explicit_plugin_execution_persists_sanitized_feedback(
    test_db, stored_session
) -> None:
    adapter = FakeACECTAdapter()
    evaluator = ACECTInspiredRubricEvaluator(
        llm_adapter=adapter,
        llm_provider="gemini",
        model_identifier="synthetic-fake-model",
        allow_experimental_override=True,
    )

    response = await evaluator.evaluate(test_db, stored_session.id)
    persisted = test_db.query(Feedback).filter_by(session_id=stored_session.id).one()

    assert response.id == persisted.id
    assert response.empathy_score == 75.0
    assert response.communication_score == 75.0
    assert response.overall_score == 75.0
    assert response.evaluator_meta["framework"] == "ACE-CT-inspired"
    assert response.evaluator_meta["publication_reproduction"] is False
    assert response.evaluator_meta["llm_provider"] == "gemini"
    assert len(response.evaluator_meta["framework_results"]["dimension_results"]) == 11
    assert "raw_model_response" not in response.model_dump_json()


@pytest.mark.asyncio
async def test_plugin_refuses_persistence_when_not_explicitly_selected(
    test_db, stored_session
) -> None:
    stored_session.evaluator_plugin = (
        "plugins.evaluators.apex_baseline_evaluator:ApexBaselineEvaluator"
    )
    test_db.commit()
    evaluator = ACECTInspiredRubricEvaluator(
        llm_adapter=FakeACECTAdapter(),
        llm_provider="openai",
        model_identifier="synthetic-fake-model",
        allow_experimental_override=True,
    )

    with pytest.raises(ACECTComputationError, match="plugin_not_explicitly_selected"):
        await evaluator.evaluate(test_db, stored_session.id)

    assert test_db.query(Feedback).count() == 0


@pytest.mark.asyncio
async def test_shared_computation_core_is_non_persisting(test_db, stored_session) -> None:
    before = _snapshot(test_db)

    result = await compute_ace_ct_evaluation(
        test_db,
        stored_session.id,
        llm_provider="openai",
        model_identifier="synthetic-fake-model",
        llm_adapter=FakeACECTAdapter(),
        allow_experimental_override=True,
    )

    after = _snapshot(test_db)
    assert after == before
    assert result.computed_feedback is not None
    assert len(result.framework_results.dimension_results) == 11
    assert test_db.query(Feedback).count() == 0


@pytest.mark.asyncio
async def test_normal_scoring_entrypoint_uses_plugin_core_and_persists_once(
    test_db, stored_session, monkeypatch
) -> None:
    calls: list[int] = []
    original_compute = ACECTInspiredRubricEvaluator.compute

    async def wrapped_compute(self, db, session_id):
        calls.append(session_id)
        return await original_compute(self, db, session_id)

    monkeypatch.setattr(ACECTInspiredRubricEvaluator, "compute", wrapped_compute)
    monkeypatch.setattr(
        "plugins.evaluators.ace_ct_inspired_evaluator.get_settings",
        lambda: type(
            "TestSettings",
            (),
            {
                "default_llm_provider": "gemini",
                "ace_ct_allow_experimental_rubric": True,
            },
        )(),
    )
    monkeypatch.setattr(
        "services.ace_ct_computation_service.resolve_evaluator_llm_adapter",
        lambda *args, **kwargs: type(
            "Resolved",
            (),
            {
                "provider": "gemini",
                "model_identifier": "synthetic-fake-model",
                "adapter": FakeACECTAdapter(),
            },
        )(),
    )

    response = await ScoringService(test_db).generate_feedback(stored_session.id)

    assert calls == [stored_session.id]
    assert response.evaluator_meta["phase"] == "ace_ct_inspired_experimental_v1"
    assert test_db.query(Feedback).count() == 1


@pytest.mark.asyncio
async def test_failure_does_not_create_or_overwrite_feedback(test_db, stored_session) -> None:
    existing = Feedback(
        session_id=stored_session.id,
        empathy_score=11,
        communication_score=12,
        spikes_completion_score=13,
        overall_score=14,
        strengths="keep-existing",
    )
    test_db.add(existing)
    test_db.commit()
    before = _snapshot(test_db)
    evaluator = ACECTInspiredRubricEvaluator(
        llm_adapter=FakeACECTAdapter(raw_response="not-json"),
        llm_provider="openai",
        model_identifier="synthetic-fake-model",
        allow_experimental_override=True,
    )

    with pytest.raises(ACECTComputationError, match="invalid_json"):
        await evaluator.evaluate(test_db, stored_session.id)

    assert _snapshot(test_db) == before
    persisted = test_db.query(Feedback).filter_by(session_id=stored_session.id).one()
    assert persisted.strengths == "keep-existing"


@pytest.mark.asyncio
async def test_pending_rubric_gate_prevents_persistence(test_db, stored_session) -> None:
    evaluator = ACECTInspiredRubricEvaluator(
        llm_adapter=FakeACECTAdapter(),
        llm_provider="openai",
        model_identifier="synthetic-fake-model",
        allow_experimental_override=False,
    )

    with pytest.raises(ACECTComputationError, match="rubric_not_approved"):
        await evaluator.evaluate(test_db, stored_session.id)

    assert test_db.query(Feedback).count() == 0
