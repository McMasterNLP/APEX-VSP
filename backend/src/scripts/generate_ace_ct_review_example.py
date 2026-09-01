"""Generate the deterministic, transcript-redacted ACE-CT review example."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from repositories.turn_repo import TurnRepository
from scripts.run_seeded_evaluator_case_study import seed_case_study_sessions
from services.evaluator_comparison_service import (
    EvaluatorComparisonService,
    build_comparison_artifact,
)
from tests.utils.ace_ct import FakeACECTAdapter, build_valid_ace_ct_payload
from tests.utils.transcript_runner import create_all_for_test_engine


def _review_payload() -> dict:
    payload = build_valid_ace_ct_payload(evidence_turn_numbers=[2, 3], score=4)
    payload["dimension_results"][0]["score"] = 3
    payload["domain_scores"][0]["mean_score"] = 3.0

    pace = payload["dimension_results"][-1]
    pace.update(
        score=None,
        insufficient_evidence=True,
        confidence=0.35,
        evidence_turn_numbers=[],
        reasoning="Timing and delivery speed are absent from the transcript.",
        improvement_recommendation=(
            "Review pacing with audio or video before assigning a native score."
        ),
    )
    payload["domain_scores"][-1].update(
        mean_score=4.0,
        scored_dimension_count=3,
        insufficient_evidence_count=1,
    )
    return payload


async def generate_review_example() -> dict:
    """Return one deterministic synthetic wrapper around a canonical comparison artifact."""

    engine = create_engine("sqlite:///:memory:")
    create_all_for_test_engine(engine)
    db = sessionmaker(bind=engine)()
    try:
        session_id = seed_case_study_sessions(db)["strong"]
        results = await EvaluatorComparisonService(
            db,
            llm_provider="gemini",
            model_identifier="synthetic-fake-model",
            llm_adapter=FakeACECTAdapter(payload=_review_payload()),
            allow_experimental_override=True,
        ).run_evaluators(session_id, ["baseline", "ace_ct_inspired"])
        deterministic_results = [
            result.model_copy(update={"runtime_ms": 0.0}) for result in results
        ]
        turns = TurnRepository(db).get_by_session(session_id)
        artifact = build_comparison_artifact(
            session_id=session_id,
            turns=turns,
            requested_evaluators=["baseline", "ace_ct_inspired"],
            results=deterministic_results,
            include_transcript=False,
            git_commit=None,
            generated_at=datetime(2026, 8, 31, 16, 0, tzinfo=UTC),
            run_id="synthetic-ace-ct-review-example",
        )
        artifact_payload = artifact.model_dump(
            mode="json",
            exclude_none=True,
        )
        ace_ct_result = next(
            result
            for result in artifact_payload["observed_results"]
            if result["evaluator_identifier"] == "ace_ct_inspired"
        )
        # Keep the example compact while showing the null policy explicitly.
        ace_ct_result["framework_results"]["dimension_results"][-1]["score"] = None
        return {
            "example_classification": "synthetic_fake_model_output",
            "experimental_evidence": False,
            "public_synthetic_fixture": "difficult_diagnosis_strong",
            "transcript_included": False,
            "purpose": (
                "Internal structural review only; not clinical validation or experimental evidence."
            ),
            "comparison_artifact": artifact_payload,
        }
    finally:
        db.close()


def main() -> int:
    print(
        json.dumps(
            asyncio.run(generate_review_example()),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
