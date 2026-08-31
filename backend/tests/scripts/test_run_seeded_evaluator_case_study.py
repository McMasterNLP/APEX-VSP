"""Reproduction tests for the four-condition seeded evaluator case study."""

from __future__ import annotations

import json
from argparse import Namespace
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from domain.entities.case import Case
from domain.entities.feedback import Feedback
from domain.entities.session import Session as SessionEntity
from domain.entities.turn import Turn
from domain.entities.user import User
from scripts.compare_session_evaluators import EXIT_INVALID_INPUT, EXIT_SUCCESS
from scripts.run_seeded_evaluator_case_study import (
    CASE_STUDY_FIXTURES,
    build_seeded_case_study,
    execute_command,
    seed_case_study_sessions,
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


def _patch_hybrids(monkeypatch, *, fail_v1: bool = False) -> None:
    async def fake_v1(self, state, session_id):
        if fail_v1:
            raise RuntimeError("raw-error-must-not-escape")
        return (
            70.0,
            71.0,
            72.0,
            71.0,
            {"phase": "hybrid_llm_v1", "status": "completed", "llm_output": {}},
        )

    async def fake_v2(self, state, session_id):
        return (
            80.0,
            81.0,
            82.0,
            81.0,
            {"phase": "hybrid_llm_v2", "status": "completed", "llm_output": {}},
        )

    monkeypatch.setattr(ScoringService, "_hybrid_llm_merge_scores", fake_v1)
    monkeypatch.setattr(ScoringService, "_hybrid_v2_llm_merge_scores", fake_v2)


def _snapshot(test_db) -> dict:
    def rows(entity):
        return [dict(row) for row in test_db.execute(select(entity.__table__)).mappings()]

    return {
        "users": rows(User),
        "cases": rows(Case),
        "sessions": rows(SessionEntity),
        "turns": rows(Turn),
        "feedback": rows(Feedback),
    }


@pytest.mark.asyncio
async def test_seeded_case_study_reuses_all_four_fixtures_without_mutation(
    test_db, monkeypatch
) -> None:
    _patch_hybrids(monkeypatch)
    session_ids = seed_case_study_sessions(test_db)
    before = _snapshot(test_db)

    artifact = await build_seeded_case_study(
        test_db,
        session_ids=session_ids,
        evaluator_identifiers=["baseline", "hybrid_v1", "hybrid_v2"],
        model_identifier="gpt-test",
        generated_at=datetime(2026, 3, 1, tzinfo=UTC),
        git_commit="a" * 40,
    )

    after = _snapshot(test_db)
    serialized = artifact.model_dump_json()
    assert after == before
    assert set(session_ids) == {"strong", "decent", "mixed", "weak"}
    assert list(artifact.condition_results) == ["strong", "decent", "mixed", "weak"]
    assert len(artifact.paper_table_rows) == 12
    assert all(row["transcript_hash"] for row in artifact.paper_table_rows)
    assert all(row["runtime_ms"] >= 0 for row in artifact.paper_table_rows)
    assert all(
        len({result.transcript_hash for result in condition.observed_results}) == 1
        for condition in artifact.condition_results.values()
    )
    assert test_db.query(Feedback).count() == 0
    assert all(session.metrics_json is None for session in test_db.query(SessionEntity).all())
    assert CASE_STUDY_FIXTURES["strong"]["transcript"][0]["text"] not in serialized
    assert "raw-error-must-not-escape" not in serialized
    assert "technical evidence, not clinical validation" in serialized
    assert "LLM judges, not clinicians or clinical experts" in serialized


@pytest.mark.asyncio
async def test_seeded_case_study_retains_partial_results(test_db, monkeypatch) -> None:
    _patch_hybrids(monkeypatch, fail_v1=True)
    session_ids = seed_case_study_sessions(test_db)

    artifact = await build_seeded_case_study(
        test_db,
        session_ids=session_ids,
        evaluator_identifiers=["baseline", "hybrid_v1", "hybrid_v2"],
        model_identifier="gpt-test",
    )

    for condition in artifact.condition_results.values():
        assert [result.status for result in condition.observed_results] == [
            "success",
            "failed",
            "success",
        ]


@pytest.mark.asyncio
async def test_cli_refuses_hybrid_calls_without_explicit_authorization(
    tmp_path, monkeypatch
) -> None:
    async def forbidden(*args, **kwargs):
        raise AssertionError("Hybrid evaluation should not start")

    monkeypatch.setattr(ScoringService, "compute_hybrid_feedback", forbidden)
    output = tmp_path / "forbidden.json"
    args = Namespace(
        evaluators="all",
        output=output,
        overwrite=False,
        allow_live_llm=False,
    )

    code = await execute_command(args)

    assert code == EXIT_INVALID_INPUT
    assert not output.exists()


@pytest.mark.asyncio
async def test_baseline_only_case_study_runs_offline(tmp_path) -> None:
    output = tmp_path / "baseline_case_study.json"
    args = Namespace(
        evaluators="baseline",
        output=output,
        overwrite=False,
        allow_live_llm=False,
    )

    code = await execute_command(args)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == EXIT_SUCCESS
    assert len(payload["condition_results"]) == 4
    assert len(payload["paper_table_rows"]) == 4
    assert all(row["evaluator_identifier"] == "baseline" for row in payload["paper_table_rows"])
