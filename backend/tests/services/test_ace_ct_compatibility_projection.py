"""Tests for explicit ACE-CT-inspired compatibility score projection."""

from __future__ import annotations

import copy
import math

import pytest

from schemas.ace_ct import ACE_CT_RUBRIC_V0_1, ACECTEvaluationResult
from services.ace_ct_results import (
    FRAMEWORK_EQUIVALENCE_WARNING,
    aggregate_ace_ct_domains,
    build_ace_ct_framework_results,
    normalize_ace_ct_score,
    project_ace_ct_compatibility_scores,
)


def _payload() -> dict:
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
                "confidence": 0.7,
                "evidence_turn_numbers": [1],
                "reasoning": "Concise rationale.",
                "improvement_recommendation": "Concise recommendation.",
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


def _evaluation(payload: dict | None = None) -> ACECTEvaluationResult:
    return ACECTEvaluationResult.model_validate(payload or _payload())


@pytest.mark.parametrize(
    ("native", "normalized"),
    [(1, 0.0), (2, 25.0), (3, 50.0), (4, 75.0), (5, 100.0)],
)
def test_native_score_normalization(native: int, normalized: float) -> None:
    assert normalize_ace_ct_score(native) == normalized


def test_normalization_preserves_null_without_imputation() -> None:
    assert normalize_ace_ct_score(None) is None


@pytest.mark.parametrize("invalid", [0, 6, 2.5, True])
def test_normalization_rejects_invalid_native_scores(invalid) -> None:
    with pytest.raises(ValueError):
        normalize_ace_ct_score(invalid)


def test_projection_uses_respond_to_emotion_and_non_null_mean() -> None:
    payload = _payload()
    payload["dimension_results"][1].update(
        score=None,
        insufficient_evidence=True,
        evidence_turn_numbers=[],
    )
    listen_scores = [
        item["score"]
        for item in payload["dimension_results"]
        if item["domain"] == "listen" and item["score"] is not None
    ]
    payload["domain_scores"][1].update(
        mean_score=math.fsum(listen_scores) / len(listen_scores),
        scored_dimension_count=len(listen_scores),
        insufficient_evidence_count=1,
    )
    evaluation = _evaluation(payload)

    projection = project_ace_ct_compatibility_scores(
        evaluation,
        apex_baseline_spikes_completion_score=87.5,
    )
    expected = (
        math.fsum(
            normalize_ace_ct_score(result.score)
            for result in evaluation.dimension_results
            if result.score is not None
        )
        / 10
    )

    assert projection.scores.empathy_score == 0.0
    assert projection.scores.communication_score == expected
    assert projection.scores.overall_score == expected
    assert projection.scores.spikes_completion_score == 87.5


def test_all_null_behavior_does_not_manufacture_canonical_scores() -> None:
    payload = _payload()
    for result in payload["dimension_results"]:
        result.update(score=None, insufficient_evidence=True, evidence_turn_numbers=[])
    for domain in payload["domain_scores"]:
        domain.update(
            mean_score=None,
            scored_dimension_count=0,
            insufficient_evidence_count=sum(
                item["domain"] == domain["domain"] for item in payload["dimension_results"]
            ),
        )

    projection = project_ace_ct_compatibility_scores(_evaluation(payload))

    assert projection.scores.empathy_score is None
    assert projection.scores.communication_score is None
    assert projection.scores.overall_score is None
    assert projection.scores.spikes_completion_score is None


def test_domain_aggregation_excludes_nulls_and_handles_all_null_domain() -> None:
    payload = _payload()
    for result in payload["dimension_results"]:
        if result["domain"] == "listen":
            result.update(score=None, insufficient_evidence=True, evidence_turn_numbers=[])
    payload["domain_scores"][1].update(
        mean_score=None,
        scored_dimension_count=0,
        insufficient_evidence_count=4,
    )
    evaluation = _evaluation(payload)

    aggregates = aggregate_ace_ct_domains(evaluation.dimension_results)

    assert aggregates[1].domain.value == "listen"
    assert aggregates[1].mean_score is None
    assert aggregates[1].scored_dimension_count == 0
    assert aggregates[1].insufficient_evidence_count == 4
    assert aggregates == evaluation.domain_scores


def test_score_sources_and_framework_warning_are_explicit() -> None:
    projection = project_ace_ct_compatibility_scores(
        _evaluation(),
        apex_baseline_spikes_completion_score=50,
    )
    sources = projection.score_sources.model_dump()

    assert sources["empathy_score"].startswith("ace_ct_inspired.dimension")
    assert "mean_of_non_null_dimensions" in sources["communication_score"]
    assert "mean_of_non_null_dimensions" in sources["overall_score"]
    assert sources["spikes_completion_score"] == (
        "apex_baseline.spikes_completion_score_not_ace_ct"
    )
    assert "ace_ct" not in sources["spikes_completion_score"].split("not_ace_ct")[0]
    assert projection.warnings == (FRAMEWORK_EQUIVALENCE_WARNING,)


def test_framework_results_receive_compatibility_source_mapping() -> None:
    evaluation = _evaluation()
    projection = project_ace_ct_compatibility_scores(
        evaluation,
        apex_baseline_spikes_completion_score=50,
    )

    framework = build_ace_ct_framework_results(
        evaluation,
        compatibility_projection=projection,
    )

    assert framework.score_sources["compatibility.empathy_score"] == (
        "ace_ct_inspired.dimension.respond_to_emotion.normalized_0_100"
    )
    assert framework.score_sources["compatibility.spikes_completion_score"] == (
        "apex_baseline.spikes_completion_score_not_ace_ct"
    )


@pytest.mark.parametrize("invalid", [-1, 101, math.nan, math.inf, True])
def test_invalid_baseline_spikes_score_is_rejected(invalid) -> None:
    with pytest.raises(ValueError, match="APEX baseline SPIKES"):
        project_ace_ct_compatibility_scores(
            _evaluation(),
            apex_baseline_spikes_completion_score=invalid,
        )


def test_projection_does_not_mutate_evaluation() -> None:
    payload = _payload()
    before = copy.deepcopy(payload)

    project_ace_ct_compatibility_scores(_evaluation(payload))

    assert payload == before
