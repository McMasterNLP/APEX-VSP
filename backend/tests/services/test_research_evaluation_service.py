"""Service and export tests for non-persisting research evaluations."""

from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from io import BytesIO

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from domain.entities.case import Case
from domain.entities.feedback import Feedback
from domain.entities.session import Session as SessionEntity
from domain.entities.turn import Turn
from domain.entities.user import User
from domain.models.evaluator_comparison import (
    EvaluatorRunResult,
    SanitizedEvaluatorError,
)
from domain.models.research_evaluation import (
    ResearchEvaluationRequest,
    ResearchExportRequest,
)
from services.evaluator_comparison_service import build_evaluator_provenance
from services.research_evaluation_service import (
    ResearchEvaluationService,
    ResearchEvaluationServiceError,
)
from services.research_export_service import ResearchExportService
from tests.services.test_research_adapters import _apex_run
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
    user = User(email="research-service@example.com", role="trainee", full_name="Research")
    case = Case(
        title="Research service case",
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
        started_at=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        ended_at=datetime(2026, 9, 1, 12, 5, tzinfo=UTC),
        duration_seconds=300,
        evaluator_plugin="plugins.evaluators.apex_baseline_evaluator:ApexBaselineEvaluator",
        evaluator_version="1.0",
        metrics_plugins='["plugins.metrics.apex_metrics:ApexMetrics"]',
        metrics_json='{"existing":true}',
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
                text="How are you feeling?",
                metrics_json='{"question_type":"open","tone":{"clear":true,"calm":true}}',
                spans_json=json.dumps(
                    [
                        {
                            "span_type": "elicitation",
                            "type": "direct",
                            "dimension": "Feeling",
                            "start_char": 0,
                            "end_char": 19,
                            "text": "How are you feeling",
                            "confidence": 0.9,
                            "provenance": "rule",
                        }
                    ]
                ),
                spikes_stage="perception",
            ),
            Turn(
                session_id=session.id,
                turn_number=2,
                role="assistant",
                text="I feel worried.",
                spans_json=json.dumps(
                    [
                        {
                            "span_type": "eo",
                            "dimension": "Feeling",
                            "explicit_or_implicit": "explicit",
                            "start_char": 7,
                            "end_char": 14,
                            "text": "worried",
                            "confidence": 0.9,
                            "provenance": "rule",
                        }
                    ]
                ),
                spikes_stage="emotion",
            ),
            Turn(
                session_id=session.id,
                user_id=user.id,
                turn_number=3,
                role="user",
                text="I understand.",
                metrics_json='{"tone":{"clear":true,"calm":true}}',
                spans_json=json.dumps(
                    [
                        {
                            "span_type": "response",
                            "type": "understanding",
                            "start_char": 2,
                            "end_char": 12,
                            "text": "understand",
                            "confidence": 0.8,
                            "provenance": "rule",
                        }
                    ]
                ),
                spikes_stage="strategy",
            ),
        ]
    )
    test_db.add(
        Feedback(
            session_id=session.id,
            empathy_score=9,
            communication_score=8,
            spikes_completion_score=7,
            overall_score=6,
            strengths="Saved learner feedback",
            evaluator_meta='{"source":"saved"}',
        )
    )
    test_db.commit()
    test_db.refresh(session)
    return session


def _service(test_db, **overrides) -> ResearchEvaluationService:
    return ResearchEvaluationService(
        test_db,
        live_execution_enabled=False,
        ace_ct_experimental_enabled=False,
        configured_models={},
        **overrides,
    )


def _database_snapshot(test_db, session_id: int) -> dict:
    return {
        "session": dict(
            test_db.execute(
                select(SessionEntity.__table__).where(SessionEntity.id == session_id)
            )
            .mappings()
            .one()
        ),
        "turns": [
            dict(row)
            for row in test_db.execute(
                select(Turn.__table__)
                .where(Turn.session_id == session_id)
                .order_by(Turn.turn_number)
            ).mappings()
        ],
        "feedback": dict(
            test_db.execute(
                select(Feedback.__table__).where(Feedback.session_id == session_id)
            )
            .mappings()
            .one()
        ),
    }


@pytest.mark.asyncio
async def test_baseline_success_hash_consistency_and_non_persistence(
    test_db, completed_session
):
    before = _database_snapshot(test_db, completed_session.id)
    response = await _service(test_db).evaluate(
        completed_session.id, ResearchEvaluationRequest()
    )
    after = _database_snapshot(test_db, completed_session.id)

    assert before == after
    assert response.transcript.raw_transcript_included is True
    assert response.results[0].transcript.raw_transcript_included is False
    assert response.results[0].status == "success"
    assert response.results[0].evaluator.identifier == "baseline"
    assert response.results[0].run.execution_mode == "offline"
    assert response.results[0].transcript.canonical_transcript_hash == (
        response.transcript.canonical_transcript_hash
    )
    assert len(response.results[0].projection.spans) == 3
    assert len(response.results[0].projection.relations) == 2


@pytest.mark.asyncio
async def test_stable_run_id_for_same_transcript_result_and_adapter(test_db, completed_session):
    service = _service(test_db)
    first = await service.evaluate(completed_session.id, ResearchEvaluationRequest())
    second = await service.evaluate(completed_session.id, ResearchEvaluationRequest())
    assert first.results[0].run.run_id == second.results[0].run.run_id


@pytest.mark.asyncio
async def test_live_call_refused_before_runner_construction(test_db, completed_session):
    def forbidden_runner(**kwargs):
        raise AssertionError("runner must not be constructed for a refused live call")

    service = _service(test_db, runner_factory=forbidden_runner)
    response = await service.evaluate(
        completed_session.id,
        ResearchEvaluationRequest(evaluator_identifiers=("hybrid_v1",)),
    )
    result = response.results[0]
    assert result.status == "refused"
    assert result.error.category == "live_execution_refused"
    assert result.framework_result is None


@pytest.mark.asyncio
async def test_multiple_results_isolate_one_evaluator_failure(test_db, completed_session):
    class FakeRunner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def run_evaluators(self, session_id, identifiers, require_completed=True):
            identifier = identifiers[0]
            if identifier == "baseline":
                return [_apex_run("baseline")]
            return [
                EvaluatorRunResult(
                    evaluator_identifier="hybrid_v1",
                    evaluator_name="ApexHybridEvaluator",
                    evaluator_version="1.0",
                    status="failed",
                    runtime_ms=1,
                    transcript_hash=_apex_run("hybrid_v1").transcript_hash,
                    provenance=build_evaluator_provenance(
                        "hybrid_v1",
                        llm_provider="openai",
                        model_identifier="synthetic-model",
                    ),
                    error=SanitizedEvaluatorError(
                        category="evaluation_failed",
                        message="Evaluator did not produce a complete review.",
                    ),
                )
            ]

    service = ResearchEvaluationService(
        test_db,
        runner_factory=lambda **kwargs: FakeRunner(**kwargs),
        live_execution_enabled=True,
        ace_ct_experimental_enabled=True,
        configured_models={"openai": "synthetic-model"},
    )
    response = await service.evaluate(
        completed_session.id,
        ResearchEvaluationRequest(
            evaluator_identifiers=("baseline", "hybrid_v1"),
            allow_live=True,
        ),
    )
    assert [result.status for result in response.results] == ["success", "failed"]
    assert response.results[1].evaluator.model_identifier == "synthetic-model"


@pytest.mark.asyncio
async def test_invalid_adapter_result_is_sanitized(test_db, completed_session):
    class InvalidRunner:
        async def run_evaluators(self, session_id, identifiers, require_completed=True):
            run = _apex_run("baseline")
            return [run.model_copy(update={"structured_feedback": None})]

    response = await _service(
        test_db, runner_factory=lambda **kwargs: InvalidRunner()
    ).evaluate(completed_session.id, ResearchEvaluationRequest())
    result = response.results[0]
    assert result.status == "failed"
    assert result.error.category == "invalid_native_result"
    assert "structured_feedback" not in result.error.message


@pytest.mark.asyncio
async def test_missing_and_incomplete_sessions_are_rejected(test_db, completed_session):
    service = _service(test_db)
    with pytest.raises(ResearchEvaluationServiceError) as missing:
        await service.evaluate(999999, ResearchEvaluationRequest())
    assert missing.value.category == "session_not_found"

    completed_session.state = "active"
    test_db.commit()
    with pytest.raises(ResearchEvaluationServiceError) as incomplete:
        await service.evaluate(completed_session.id, ResearchEvaluationRequest())
    assert incomplete.value.category == "session_incomplete"


def test_descriptors_declare_capabilities_and_live_availability(test_db):
    descriptors = _service(test_db).descriptors().evaluators
    by_id = {descriptor.identifier: descriptor for descriptor in descriptors}
    assert by_id["baseline"].default_selected is True
    assert by_id["baseline"].availability == "available"
    assert by_id["baseline"].capabilities.outputs.character_spans is True
    assert by_id["hybrid_v1"].availability == "server_live_disabled"
    assert by_id["ace_ct_inspired"].capabilities.outputs.dimension_ratings is True


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["full", "framework_native", "projection"])
async def test_json_exports_are_sanitized_and_profiled(
    profile, test_db, completed_session
):
    response = await _service(test_db).evaluate(
        completed_session.id, ResearchEvaluationRequest()
    )
    artifact = ResearchExportService().render(
        ResearchExportRequest(profile=profile, envelopes=response.results),
        response.transcript_turns,
    )
    payload = json.loads(artifact.content)
    serialized = artifact.content.decode("utf-8")
    assert artifact.media_type == "application/json"
    assert payload["profile"] == profile
    assert payload["raw_transcript_included"] is False
    assert "I feel worried." not in serialized
    assert '"quoted_text": "worried"' not in serialized
    if profile == "framework_native":
        assert "framework_result" in payload["results"][0]
        assert "projection" not in payload["results"][0]
    if profile == "projection":
        assert "projection" in payload["results"][0]
        assert "framework_result" not in payload["results"][0]


@pytest.mark.asyncio
async def test_tabular_export_is_multi_table_zip_not_flat_lossless_csv(
    test_db, completed_session
):
    response = await _service(test_db).evaluate(
        completed_session.id, ResearchEvaluationRequest()
    )
    artifact = ResearchExportService().render(
        ResearchExportRequest(profile="tabular", envelopes=response.results),
        response.transcript_turns,
    )
    assert artifact.media_type == "application/zip"
    with zipfile.ZipFile(BytesIO(artifact.content)) as bundle:
        names = set(bundle.namelist())
        assert names >= {
            "runs.csv",
            "spans.csv",
            "turn_labels.csv",
            "relations.csv",
            "metrics.csv",
            "findings.csv",
            "limitations.csv",
        }
        runs = bundle.read("runs.csv").decode()
        spans = bundle.read("spans.csv").decode()
        assert "schema_version,run_id,transcript_hash" in runs
        assert "I feel worried." not in spans
        assert ",worried," not in spans
