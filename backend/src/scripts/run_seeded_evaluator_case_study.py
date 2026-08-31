"""Reproduce the four-condition evaluator case study in an ephemeral local database."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import get_settings
from domain.entities.case import Case
from domain.entities.session import Session as SessionEntity
from domain.entities.turn import Turn
from domain.entities.user import User
from domain.models.evaluator_comparison import SeededCaseStudyArtifact
from repositories.turn_repo import TurnRepository
from scripts.compare_session_evaluators import (
    EXIT_INVALID_INPUT,
    EXIT_PARTIAL_FAILURE,
    EXIT_SUCCESS,
    get_git_commit,
    parse_evaluator_selection,
)
from services.evaluator_comparison_service import (
    EvaluatorComparisonService,
    build_comparison_artifact,
)
from tests.fixtures.generated_validation_cases import (
    TEST_DIFFICULT_DIAGNOSIS_DECENT,
    TEST_DIFFICULT_DIAGNOSIS_MIXED,
    TEST_DIFFICULT_DIAGNOSIS_STRONG,
    TEST_DIFFICULT_DIAGNOSIS_WEAK,
)
from tests.utils.transcript_runner import create_all_for_test_engine

CASE_STUDY_FIXTURES = {
    "strong": TEST_DIFFICULT_DIAGNOSIS_STRONG,
    "decent": TEST_DIFFICULT_DIAGNOSIS_DECENT,
    "mixed": TEST_DIFFICULT_DIAGNOSIS_MIXED,
    "weak": TEST_DIFFICULT_DIAGNOSIS_WEAK,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the four public seeded transcript conditions in a local database."
    )
    parser.add_argument("--evaluators", default="all")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--allow-live-llm",
        action="store_true",
        help="Explicitly authorize model calls for hybrid evaluators.",
    )
    return parser


def seed_case_study_sessions(db: Session) -> dict[str, int]:
    """Seed the existing public fixtures into an isolated caller-owned database."""
    user = User(
        email="seeded-case-study@example.invalid",
        role="trainee",
        full_name="Seeded Case Study",
    )
    case = Case(
        title="Seeded difficult diagnosis case study",
        description="Local technical evaluator comparison.",
        script="Fixture-owned transcript; patient generation is not used.",
        difficulty_level="intermediate",
        category="test",
        patient_background="Synthetic public test fixture.",
        expected_spikes_flow=None,
    )
    db.add_all([user, case])
    db.commit()

    session_ids: dict[str, int] = {}
    for condition, fixture in CASE_STUDY_FIXTURES.items():
        session = SessionEntity(
            user_id=user.id,
            case_id=case.id,
            state="completed",
            evaluator_plugin="plugins.evaluators.apex_baseline_evaluator:ApexBaselineEvaluator",
            evaluator_version="1.0",
            patient_model_plugin="fixture-only",
            patient_model_version="1.0",
            metrics_plugins="[]",
            metrics_json=None,
        )
        db.add(session)
        db.commit()
        for turn_data in fixture["transcript"]:
            role = turn_data["role"]
            db.add(
                Turn(
                    session_id=session.id,
                    user_id=user.id if role == "user" else None,
                    turn_number=turn_data["turn_number"],
                    role=role,
                    text=turn_data["text"],
                    metrics_json=(
                        json.dumps(turn_data.get("metrics_json"), ensure_ascii=False)
                        if turn_data.get("metrics_json") is not None
                        else None
                    ),
                    spans_json=(
                        json.dumps(turn_data.get("spans_json"), ensure_ascii=False)
                        if turn_data.get("spans_json") is not None
                        else None
                    ),
                    relations_json=(
                        json.dumps(turn_data.get("relations_json"), ensure_ascii=False)
                        if turn_data.get("relations_json") is not None
                        else None
                    ),
                    spikes_stage=turn_data.get("expected_spikes"),
                )
            )
        db.commit()
        session_ids[condition] = session.id
    return session_ids


async def build_seeded_case_study(
    db: Session,
    *,
    session_ids: dict[str, int],
    evaluator_identifiers: list[str],
    model_identifier: str | None,
    generated_at: datetime | None = None,
    git_commit: str | None = None,
) -> SeededCaseStudyArtifact:
    """Run the same evaluator set for every seeded condition and aggregate safe output."""
    condition_results = {}
    paper_rows: list[dict] = []
    timestamp = generated_at or datetime.now(UTC)
    for condition in CASE_STUDY_FIXTURES:
        session_id = session_ids[condition]
        service = EvaluatorComparisonService(db, model_identifier=model_identifier)
        results = await service.run_evaluators(session_id, evaluator_identifiers)
        turns = TurnRepository(db).get_by_session(session_id)
        artifact = build_comparison_artifact(
            session_id=session_id,
            turns=turns,
            requested_evaluators=evaluator_identifiers,
            results=results,
            include_transcript=False,
            git_commit=git_commit,
            generated_at=timestamp,
            run_id=f"seeded-{condition}",
        )
        condition_results[condition] = artifact
        for result in artifact.observed_results:
            scores = result.scores
            paper_rows.append(
                {
                    "condition": condition,
                    "transcript_hash": artifact.transcript_hash,
                    "evaluator_identifier": result.evaluator_identifier,
                    "evaluator_name": result.evaluator_name,
                    "evaluator_version": result.evaluator_version,
                    "status": result.status,
                    "runtime_ms": result.runtime_ms,
                    "empathy_score": scores.empathy_score if scores else None,
                    "communication_score": scores.communication_score if scores else None,
                    "spikes_completion_score": (scores.spikes_completion_score if scores else None),
                    "overall_score": scores.overall_score if scores else None,
                    "error_category": result.error.category if result.error else None,
                }
            )

    return SeededCaseStudyArtifact(
        schema_version="1.0",
        generated_at=timestamp.isoformat().replace("+00:00", "Z"),
        git_commit=git_commit,
        study_type="technical_evaluator_case_study",
        requested_evaluators=evaluator_identifiers,
        condition_results=condition_results,
        paper_table_rows=paper_rows,
        methodology_notes=[
            "All evaluators within a condition received the same stored transcript hash.",
            "Strong, decent, mixed, and weak conditions reuse existing public test fixtures.",
            "The database is ephemeral in-memory SQLite and is not production or shared data.",
        ],
        limitations=[
            "This case study is technical evidence, not clinical validation.",
            "External comparison files are outputs from LLM judges, not clinicians or clinical experts.",
            "LLM-judge agreement must not be interpreted as clinical correctness.",
            "No external LLM-judge comparison is calculated here because merged evaluator scores are not directly equivalent to raw judge scores.",
        ],
    )


def _write_output(path: Path, artifact: SeededCaseStudyArtifact, *, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"
    with path.open(mode, encoding="utf-8", newline="\n") as handle:
        handle.write(artifact.model_dump_json(indent=2, exclude_none=True))
        handle.write("\n")


async def execute_command(args: argparse.Namespace) -> int:
    try:
        evaluators = parse_evaluator_selection(args.evaluators)
        includes_hybrid = any(identifier.startswith("hybrid_") for identifier in evaluators)
        if includes_hybrid and not args.allow_live_llm:
            raise ValueError(
                "Hybrid case-study runs require explicit --allow-live-llm authorization."
            )
        if args.output.exists() and not args.overwrite:
            raise FileExistsError("Output already exists; pass --overwrite to replace it.")

        engine = create_engine("sqlite:///:memory:")
        create_all_for_test_engine(engine)
        db = sessionmaker(bind=engine)()
        try:
            session_ids = seed_case_study_sessions(db)
            artifact = await build_seeded_case_study(
                db,
                session_ids=session_ids,
                evaluator_identifiers=evaluators,
                model_identifier=(get_settings().openai_model_id if includes_hybrid else None),
                git_commit=get_git_commit(),
            )
            _write_output(args.output, artifact, overwrite=args.overwrite)
        finally:
            db.close()
        failed = sum(
            result.status == "failed"
            for condition in artifact.condition_results.values()
            for result in condition.observed_results
        )
        return EXIT_PARTIAL_FAILURE if failed else EXIT_SUCCESS
    except (ValueError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INVALID_INPUT


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(execute_command(args))
    except Exception:  # noqa: BLE001 - boundary intentionally omits raw errors
        print("Seeded case study failed without producing an artifact.", file=sys.stderr)
        return EXIT_INVALID_INPUT


if __name__ == "__main__":
    raise SystemExit(main())
