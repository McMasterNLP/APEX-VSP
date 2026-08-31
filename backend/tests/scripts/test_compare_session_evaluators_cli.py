"""CLI tests for privacy, exit behavior, and database non-mutation."""

from __future__ import annotations

import json
from argparse import Namespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from domain.entities.case import Case
from domain.entities.feedback import Feedback
from domain.entities.session import Session as SessionEntity
from domain.entities.turn import Turn
from domain.entities.user import User
from scripts.compare_session_evaluators import (
    EXIT_INVALID_INPUT,
    EXIT_PARTIAL_FAILURE,
    EXIT_SUCCESS,
    build_parser,
    execute_command,
    parse_evaluator_selection,
)
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
    user = User(email="private-person@example.com", role="trainee", full_name="Private Person")
    case = Case(
        title="Private case title",
        description="d",
        script="s",
        difficulty_level="intermediate",
        category="test",
        patient_background="private background",
        expected_spikes_flow=None,
    )
    test_db.add_all([user, case])
    test_db.commit()
    session = SessionEntity(
        user_id=user.id,
        case_id=case.id,
        state="completed",
        evaluator_plugin="plugins.evaluators.apex_baseline_evaluator:ApexBaselineEvaluator",
        evaluator_version="1.0",
        patient_model_plugin="patient.test",
        patient_model_version="1.0",
        metrics_plugins='["metric.test"]',
        metrics_json='{"must":"remain"}',
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
                text="This exact private clinician sentence must stay out.",
                metrics_json='{"question_type":"open"}',
                spans_json="[]",
                spikes_stage="perception",
            ),
            Turn(
                session_id=session.id,
                turn_number=2,
                role="assistant",
                text="This exact private patient sentence must stay out.",
                spans_json=json.dumps(
                    [
                        {
                            "span_type": "eo",
                            "dimension": "Feeling",
                            "text": "private patient sentence",
                        }
                    ]
                ),
                spikes_stage="emotion",
            ),
        ]
    )
    test_db.add(
        Feedback(
            session_id=session.id,
            empathy_score=1.0,
            communication_score=2.0,
            spikes_completion_score=3.0,
            overall_score=4.0,
            strengths="Existing feedback",
        )
    )
    test_db.commit()
    test_db.refresh(session)
    return session


def _args(session_id: int, output, **updates) -> Namespace:
    values = {
        "session_id": session_id,
        "evaluators": "baseline",
        "output": output,
        "overwrite": False,
        "include_transcript": False,
        "allow_active_session": False,
        "csv_summary": None,
        "llm_provider": None,
        "model_identifier": None,
    }
    values.update(updates)
    return Namespace(**values)


def _snapshot(test_db, session_id: int) -> dict:
    return {
        "session": dict(
            test_db.execute(select(SessionEntity.__table__).where(SessionEntity.id == session_id))
            .mappings()
            .one()
        ),
        "turns": [
            dict(row)
            for row in test_db.execute(
                select(Turn.__table__).where(Turn.session_id == session_id)
            ).mappings()
        ],
        "feedback": [
            dict(row)
            for row in test_db.execute(
                select(Feedback.__table__).where(Feedback.session_id == session_id)
            ).mappings()
        ],
        "counts": {
            "users": test_db.query(User).count(),
            "cases": test_db.query(Case).count(),
            "sessions": test_db.query(SessionEntity).count(),
            "turns": test_db.query(Turn).count(),
            "feedback": test_db.query(Feedback).count(),
        },
    }


def _patch_hybrids(monkeypatch, *, fail_v1: bool = False) -> None:
    async def fake_v1(self, state, session_id):
        if fail_v1:
            raise RuntimeError("credential-like-private-detail")
        return (
            70.0,
            70.0,
            70.0,
            70.0,
            {"phase": "hybrid_llm_v1", "status": "completed", "llm_output": {}},
        )

    async def fake_v2(self, state, session_id):
        return (
            80.0,
            80.0,
            80.0,
            80.0,
            {"phase": "hybrid_llm_v2", "status": "completed", "llm_output": {}},
        )

    monkeypatch.setattr(ScoringService, "_hybrid_llm_merge_scores", fake_v1)
    monkeypatch.setattr(ScoringService, "_hybrid_v2_llm_merge_scores", fake_v2)


def test_argument_validation_requires_session_and_output() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_all_remains_backward_compatible_and_ace_ct_is_explicit() -> None:
    assert parse_evaluator_selection("all") == ["baseline", "hybrid_v1", "hybrid_v2"]
    assert parse_evaluator_selection("baseline,ace_ct_inspired") == [
        "baseline",
        "ace_ct_inspired",
    ]


def test_parser_accepts_provider_and_safe_model_override(tmp_path) -> None:
    args = build_parser().parse_args(
        [
            "--session-id",
            "1",
            "--evaluators",
            "ace_ct_inspired",
            "--llm-provider",
            "gemini",
            "--model-identifier",
            "gemini-test",
            "--output",
            str(tmp_path / "out.json"),
        ]
    )

    assert args.llm_provider == "gemini"
    assert args.model_identifier == "gemini-test"


@pytest.mark.asyncio
async def test_baseline_comparison_does_not_load_model_settings(
    test_db, completed_session, tmp_path, monkeypatch
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("baseline comparison must not load model settings")

    monkeypatch.setattr(
        "scripts.compare_session_evaluators.get_configured_model_identifier",
        forbidden,
    )

    code = await execute_command(
        _args(completed_session.id, tmp_path / "baseline.json"),
        test_db,
    )

    assert code == EXIT_SUCCESS


@pytest.mark.asyncio
async def test_unknown_evaluator_returns_invalid_input(
    test_db, completed_session, tmp_path
) -> None:
    code = await execute_command(
        _args(completed_session.id, tmp_path / "out.json", evaluators="unknown"),
        test_db,
    )

    assert code == EXIT_INVALID_INPUT
    assert not (tmp_path / "out.json").exists()


@pytest.mark.asyncio
async def test_completed_session_is_required_by_default(
    test_db, completed_session, tmp_path
) -> None:
    completed_session.state = "active"
    test_db.commit()

    code = await execute_command(_args(completed_session.id, tmp_path / "out.json"), test_db)

    assert code == EXIT_INVALID_INPUT
    assert not (tmp_path / "out.json").exists()


@pytest.mark.asyncio
async def test_output_overwrite_requires_explicit_flag(
    test_db, completed_session, tmp_path
) -> None:
    output = tmp_path / "out.json"
    output.write_text("keep", encoding="utf-8")

    code = await execute_command(_args(completed_session.id, output), test_db)

    assert code == EXIT_INVALID_INPUT
    assert output.read_text(encoding="utf-8") == "keep"


@pytest.mark.asyncio
async def test_privacy_defaults_valid_json_and_database_nonmutation(
    test_db, completed_session, tmp_path
) -> None:
    output = tmp_path / "comparison.json"
    before = _snapshot(test_db, completed_session.id)

    code = await execute_command(_args(completed_session.id, output), test_db)

    after = _snapshot(test_db, completed_session.id)
    payload = json.loads(output.read_text(encoding="utf-8"))
    serialized = json.dumps(payload)
    assert code == EXIT_SUCCESS
    assert after == before
    assert payload["schema_version"] == "1.0"
    assert payload["anonymized_session_id"].startswith("session-")
    assert "canonical_transcript" not in payload
    assert "private-person@example.com" not in serialized
    assert "Private Person" not in serialized
    assert "This exact private clinician sentence" not in serialized
    assert "This exact private patient sentence" not in serialized
    assert "private patient sentence" not in serialized
    assert "session_id" not in payload


@pytest.mark.asyncio
async def test_include_transcript_is_explicit_opt_in(test_db, completed_session, tmp_path) -> None:
    output = tmp_path / "with_transcript.json"

    code = await execute_command(
        _args(completed_session.id, output, include_transcript=True),
        test_db,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == EXIT_SUCCESS
    assert payload["canonical_transcript"][0]["text"].startswith("This exact private")
    assert any("explicitly included" in warning for warning in payload["warnings"])


@pytest.mark.asyncio
async def test_partial_failure_writes_artifact_before_partial_exit(
    test_db, completed_session, tmp_path, monkeypatch
) -> None:
    _patch_hybrids(monkeypatch, fail_v1=True)
    output = tmp_path / "partial.json"

    code = await execute_command(
        _args(completed_session.id, output, evaluators="all"),
        test_db,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == EXIT_PARTIAL_FAILURE
    assert [result["status"] for result in payload["observed_results"]] == [
        "success",
        "failed",
        "success",
    ]
    assert "credential-like-private-detail" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_optional_csv_summary_and_output_path_protection(
    test_db, completed_session, tmp_path
) -> None:
    output = tmp_path / "comparison.json"
    csv_output = tmp_path / "comparison.csv"

    code = await execute_command(
        _args(completed_session.id, output, csv_summary=csv_output),
        test_db,
    )

    csv_text = csv_output.read_text(encoding="utf-8")
    assert code == EXIT_SUCCESS
    assert output.exists()
    assert csv_text.splitlines()[0].startswith("schema_version,run_id,anonymized_session_id")
    assert "This exact private" not in csv_text
    assert "private-person@example.com" not in csv_text

    protected_json = tmp_path / "protected.json"
    protected_csv = tmp_path / "protected.csv"
    protected_csv.write_text("keep", encoding="utf-8")
    protected_code = await execute_command(
        _args(completed_session.id, protected_json, csv_summary=protected_csv),
        test_db,
    )
    assert protected_code == EXIT_INVALID_INPUT
    assert not protected_json.exists()
    assert protected_csv.read_text(encoding="utf-8") == "keep"
