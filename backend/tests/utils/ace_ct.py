"""Synthetic fake-adapter helpers for ACE-CT-inspired tests only."""

from __future__ import annotations

import json
import math

from schemas.ace_ct import ACE_CT_RUBRIC_V0_1


def build_valid_ace_ct_payload(
    *,
    evidence_turn_numbers: list[int] | None = None,
    score: int = 4,
) -> dict:
    evidence = evidence_turn_numbers or [1]
    dimensions = []
    scores_by_domain: dict[str, list[int]] = {}
    for spec in ACE_CT_RUBRIC_V0_1.dimensions:
        dimensions.append(
            {
                "dimension_id": spec.identifier.value,
                "domain": spec.domain.value,
                "score": score,
                "insufficient_evidence": False,
                "assessability": spec.assessability.value,
                "confidence": 0.8,
                "evidence_turn_numbers": evidence,
                "reasoning": "Synthetic concise rationale.",
                "improvement_recommendation": "Synthetic concise recommendation.",
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
            "notes": ["Synthetic transcript-only result."],
            "official_model_reproduction": False,
        },
    }


class FakeACECTAdapter:
    model_id = "synthetic-fake-model"

    def __init__(self, payload: dict | None = None, *, raw_response: str | None = None):
        self.payload = payload or build_valid_ace_ct_payload()
        self.raw_response = raw_response
        self.calls: list[dict] = []

    async def generate_response(self, prompt: str, **kwargs) -> str:
        self.calls.append({"prompt": prompt, **kwargs})
        return self.raw_response if self.raw_response is not None else json.dumps(self.payload)
