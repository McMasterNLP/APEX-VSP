"""Safety and reproducibility checks for the committed review example."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.generate_ace_ct_review_example import generate_review_example
from scripts.run_seeded_evaluator_case_study import CASE_STUDY_FIXTURES

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_PATH = REPOSITORY_ROOT / "docs/research/examples/ace_ct_comparison_example.json"


@pytest.mark.asyncio
async def test_committed_example_is_deterministically_generated() -> None:
    committed = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    assert committed == await generate_review_example()


def test_example_is_clearly_synthetic_complete_and_transcript_redacted() -> None:
    payload = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    serialized = json.dumps(payload)
    artifact = payload["comparison_artifact"]
    ace_ct = next(
        result
        for result in artifact["observed_results"]
        if result["evaluator_identifier"] == "ace_ct_inspired"
    )
    framework = ace_ct["framework_results"]

    assert payload["example_classification"] == "synthetic_fake_model_output"
    assert payload["experimental_evidence"] is False
    assert payload["transcript_included"] is False
    assert "canonical_transcript" not in artifact
    assert len(framework["dimension_results"]) == 11
    assert len(framework["domain_scores"]) == 4
    assert framework["assessability_counts"]["insufficient_evidence"] == 1
    assert framework["dimension_results"][-1]["score"] is None
    assert framework["dimension_results"][-1]["evidence_turn_numbers"] == []
    assert framework["dimension_results"][0]["evidence_turn_numbers"] == [2, 3]
    assert "compatibility.spikes_completion_score" in framework["score_sources"]
    assert len({result["transcript_hash"] for result in artifact["observed_results"]}) == 1

    for fixture in CASE_STUDY_FIXTURES.values():
        for turn in fixture["transcript"]:
            assert turn["text"] not in serialized
    for forbidden in (
        "raw_model_response",
        "BEGIN INTERLEAVED TRANSCRIPT",
        "api_key",
        '"session_id":',
        '"user_id":',
    ):
        assert forbidden not in serialized
