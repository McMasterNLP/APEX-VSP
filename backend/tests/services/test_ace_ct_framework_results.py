"""Framework results survive service, sanitization, and canonical JSON export."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime

import pytest

from domain.models.evaluator_comparison import EvaluatorRunResult
from schemas.ace_ct import ACE_CT_RUBRIC_V0_1, ACECTEvaluationSuccess
from services.ace_ct_evaluator_service import ACECTEvaluatorService
from services.ace_ct_results import build_ace_ct_framework_results
from services.ace_ct_transcript import project_ace_ct_transcript
from services.evaluator_comparison_service import (
    build_comparison_artifact,
    build_evaluator_provenance,
    sanitize_evaluator_result,
)


class FakeAdapter:
    def __init__(self, payload: dict):
        self.payload = payload

    async def generate_response(self, *args, **kwargs) -> str:
        return json.dumps(self.payload)


def _source_turns() -> list[dict]:
    return [
        {
            "turn_number": 1,
            "role": "assistant",
            "text": "PRIVATE EXACT PATIENT TURN",
            "id": 501,
            "user_id": 99,
        },
        {
            "turn_number": 2,
            "role": "user",
            "text": "Can you tell me more?",
            "id": 502,
            "user_id": 99,
        },
    ]


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
                "confidence": 0.8,
                "evidence_turn_numbers": [1, 2],
                "reasoning": (
                    "PRIVATE EXACT PATIENT TURN" if index == 1 else "Concise safe rationale."
                ),
                "improvement_recommendation": "Can you tell me more?",
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


@pytest.mark.asyncio
async def test_framework_results_survive_service_run_sanitization_and_json() -> None:
    source_turns = _source_turns()
    transcript = project_ace_ct_transcript(source_turns)
    service_result = await ACECTEvaluatorService(FakeAdapter(_valid_payload())).evaluate(
        transcript,
        ACE_CT_RUBRIC_V0_1,
        allow_experimental_override=True,
    )
    assert isinstance(service_result, ACECTEvaluationSuccess)

    framework_results = build_ace_ct_framework_results(service_result.evaluation)
    run_result = EvaluatorRunResult(
        evaluator_identifier="ace_ct_inspired",
        evaluator_name="ACECTInspiredRubricEvaluator",
        evaluator_version="0.1.0-experimental",
        status="success",
        runtime_ms=1.25,
        transcript_hash=transcript.transcript_hash,
        provenance=build_evaluator_provenance(
            "ace_ct_inspired",
            llm_provider="gemini",
            model_identifier="gemini-fake",
        ),
        framework_results=framework_results,
    )

    sanitized = sanitize_evaluator_result(
        run_result,
        raw_turn_texts={turn["text"] for turn in source_turns},
    )
    artifact = build_comparison_artifact(
        session_id=42,
        turns=source_turns,
        requested_evaluators=["ace_ct_inspired"],
        results=[run_result],
        generated_at=datetime(2026, 8, 31, tzinfo=UTC),
        run_id="framework-test",
    )
    payload = json.loads(artifact.model_dump_json(exclude_none=True))
    framework_payload = payload["observed_results"][0]["framework_results"]

    assert len(framework_payload["dimension_results"]) == 11
    assert len(framework_payload["domain_scores"]) == 4
    assert framework_payload["framework"] == "ACE-CT-inspired"
    assert framework_payload["publication_reproduction"] is False
    assert framework_payload["assessability_counts"] == {
        "text_assessable": 8,
        "partially_assessable": 3,
        "not_assessable": 0,
        "scored": 11,
        "insufficient_evidence": 0,
    }
    assert framework_payload["dimension_results"][0]["evidence_turn_numbers"] == [1, 2]
    assert "PRIVATE EXACT PATIENT TURN" not in json.dumps(framework_payload)
    assert "Can you tell me more?" not in json.dumps(framework_payload)
    assert "[TRANSCRIPT_TEXT_REDACTED]" in json.dumps(framework_payload)
    assert "raw_model_response" not in json.dumps(framework_payload)
    assert "prompt" not in framework_payload
    assert sanitized.framework_results == artifact.observed_results[0].framework_results


def test_legacy_result_without_framework_keeps_csv_contract_unchanged() -> None:
    columns_before = (
        "schema_version,run_id,anonymized_session_id,transcript_hash,evaluator_name,"
        "evaluator_version,status,runtime_ms,empathy_score,communication_score,"
        "spikes_completion_score,overall_score,error_category"
    )

    from services.evaluator_comparison_service import CSV_SUMMARY_COLUMNS

    assert ",".join(CSV_SUMMARY_COLUMNS) == columns_before
