"""Strict validation tests for ACE-CT-inspired evaluator output."""

from __future__ import annotations

import copy
import math

import pytest
from pydantic import ValidationError

from schemas.ace_ct import ACE_CT_RUBRIC_V0_1, ACECTEvaluationResult


def _valid_payload() -> dict:
    dimensions = []
    scores_by_domain: dict[str, list[int]] = {}
    for index, spec in enumerate(ACE_CT_RUBRIC_V0_1.dimensions, start=1):
        score = ((index - 1) % 5) + 1
        dimensions.append(
            {
                "dimension_id": spec.identifier.value,
                "domain": spec.domain.value,
                "score": score,
                "insufficient_evidence": False,
                "assessability": spec.assessability.value,
                "confidence": 0.75,
                "evidence_turn_numbers": [1, 3],
                "reasoning": "Concise transcript-based reasoning.",
                "improvement_recommendation": "A concise improvement recommendation.",
                "modality_limitation_notes": list(spec.modality_limitations),
            }
        )
        scores_by_domain.setdefault(spec.domain.value, []).append(score)

    domains = []
    for domain in ("respond", "listen", "speak", "general"):
        scores = scores_by_domain[domain]
        domains.append(
            {
                "domain": domain,
                "mean_score": math.fsum(scores) / len(scores),
                "scored_dimension_count": len(scores),
                "insufficient_evidence_count": 0,
            }
        )

    return {
        "framework_name": "ACE-CT-inspired",
        "implementation_type": "experimental_transcript_rubric",
        "validation_status": "experimental_unvalidated",
        "publication_reproduction": False,
        "rubric_version": ACE_CT_RUBRIC_V0_1.rubric_version,
        "approval_status": ACE_CT_RUBRIC_V0_1.approval_status.value,
        "dimension_results": dimensions,
        "domain_scores": domains,
        "score_sources": {
            "dimension_scores": "experimental_llm_transcript_rubric",
            "domain_scores": "arithmetic_mean_of_non_null_dimensions",
            "compatibility_scores": "not_computed_in_model_response",
        },
        "limitations": {
            "transcript_only": True,
            "missing_modalities": ["audio", "video", "timing", "overlap"],
            "notes": ["Transcript-only experimental evaluation."],
            "official_model_reproduction": False,
        },
    }


def _validate(payload: dict) -> ACECTEvaluationResult:
    return ACECTEvaluationResult.model_validate(payload)


def test_valid_complete_evaluation_is_accepted() -> None:
    result = _validate(_valid_payload())

    assert len(result.dimension_results) == 11
    assert [score.domain.value for score in result.domain_scores] == [
        "respond",
        "listen",
        "speak",
        "general",
    ]
    assert result.publication_reproduction is False


def test_missing_dimension_is_rejected() -> None:
    payload = _valid_payload()
    payload["dimension_results"].pop()

    with pytest.raises(ValidationError, match="exactly 11"):
        _validate(payload)


def test_duplicate_dimension_is_rejected() -> None:
    payload = _valid_payload()
    payload["dimension_results"][-1] = copy.deepcopy(payload["dimension_results"][0])

    with pytest.raises(ValidationError, match="must be unique"):
        _validate(payload)


def test_unknown_dimension_is_rejected() -> None:
    payload = _valid_payload()
    payload["dimension_results"][0]["dimension_id"] = "unknown"

    with pytest.raises(ValidationError):
        _validate(payload)


def test_unstable_dimension_order_is_rejected() -> None:
    payload = _valid_payload()
    payload["dimension_results"][0], payload["dimension_results"][1] = (
        payload["dimension_results"][1],
        payload["dimension_results"][0],
    )

    with pytest.raises(ValidationError, match="stable rubric order"):
        _validate(payload)


def test_returned_domain_must_match_rubric() -> None:
    payload = _valid_payload()
    payload["dimension_results"][0]["domain"] = "listen"

    with pytest.raises(ValidationError, match="does not match rubric"):
        _validate(payload)


def test_returned_assessability_must_match_rubric() -> None:
    payload = _valid_payload()
    payload["dimension_results"][0]["assessability"] = "text_assessable"

    with pytest.raises(ValidationError, match="assessability.*does not match rubric"):
        _validate(payload)


@pytest.mark.parametrize("score", [0, 6, 2.5, "3", True])
def test_invalid_scores_are_rejected(score: object) -> None:
    payload = _valid_payload()
    payload["dimension_results"][0]["score"] = score

    with pytest.raises(ValidationError):
        _validate(payload)


def test_null_score_requires_explicit_insufficient_evidence() -> None:
    payload = _valid_payload()
    payload["dimension_results"][0]["score"] = None

    with pytest.raises(ValidationError, match="requires insufficient_evidence=true"):
        _validate(payload)


def test_scored_dimension_rejects_insufficient_evidence_flag() -> None:
    payload = _valid_payload()
    payload["dimension_results"][0]["insufficient_evidence"] = True

    with pytest.raises(ValidationError, match="requires insufficient_evidence=false"):
        _validate(payload)


def test_null_score_with_consistent_domain_aggregation_is_accepted() -> None:
    payload = _valid_payload()
    payload["dimension_results"][0]["score"] = None
    payload["dimension_results"][0]["insufficient_evidence"] = True
    payload["dimension_results"][0]["evidence_turn_numbers"] = []
    payload["domain_scores"][0].update(
        mean_score=None,
        scored_dimension_count=0,
        insufficient_evidence_count=1,
    )

    result = _validate(payload)

    assert result.dimension_results[0].score is None
    assert result.domain_scores[0].mean_score is None


@pytest.mark.parametrize("confidence", [-0.01, 1.01, math.nan, math.inf, -math.inf])
def test_confidence_must_be_finite_and_between_zero_and_one(confidence: float) -> None:
    payload = _valid_payload()
    payload["dimension_results"][0]["confidence"] = confidence

    with pytest.raises(ValidationError):
        _validate(payload)


@pytest.mark.parametrize("turns", [[3, 1], [1, 1], [0], [-1], [True], ["1"]])
def test_evidence_turn_numbers_must_be_positive_unique_and_sorted(turns: list) -> None:
    payload = _valid_payload()
    payload["dimension_results"][0]["evidence_turn_numbers"] = turns

    with pytest.raises(ValidationError, match="Evidence turn numbers"):
        _validate(payload)


def test_reasoning_and_improvement_text_are_bounded() -> None:
    reasoning_payload = _valid_payload()
    reasoning_payload["dimension_results"][0]["reasoning"] = "r" * 501
    with pytest.raises(ValidationError):
        _validate(reasoning_payload)

    improvement_payload = _valid_payload()
    improvement_payload["dimension_results"][0]["improvement_recommendation"] = "i" * 401
    with pytest.raises(ValidationError):
        _validate(improvement_payload)


def test_modality_notes_are_bounded() -> None:
    payload = _valid_payload()
    payload["dimension_results"][0]["modality_limitation_notes"] = ["x" * 301]

    with pytest.raises(ValidationError, match="Modality limitation notes"):
        _validate(payload)


def test_every_domain_must_appear_once_in_stable_order() -> None:
    missing = _valid_payload()
    missing["domain_scores"].pop()
    with pytest.raises(ValidationError, match="every domain score exactly once"):
        _validate(missing)

    reordered = _valid_payload()
    reordered["domain_scores"][0], reordered["domain_scores"][1] = (
        reordered["domain_scores"][1],
        reordered["domain_scores"][0],
    )
    with pytest.raises(ValidationError, match="stable domain order"):
        _validate(reordered)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("mean_score", 5.0, "Mean score"),
        ("scored_dimension_count", 0, "Scored dimension count"),
        ("insufficient_evidence_count", 1, "Insufficient-evidence count"),
    ],
)
def test_domain_aggregates_must_match_dimensions(field: str, value: object, message: str) -> None:
    payload = _valid_payload()
    payload["domain_scores"][1][field] = value

    with pytest.raises(ValidationError, match=message):
        _validate(payload)


def test_framework_cannot_claim_official_reproduction() -> None:
    payload = _valid_payload()
    payload["publication_reproduction"] = True

    with pytest.raises(ValidationError):
        _validate(payload)


def test_extra_raw_output_field_is_rejected() -> None:
    payload = _valid_payload()
    payload["raw_model_response"] = "must not be retained"

    with pytest.raises(ValidationError):
        _validate(payload)
