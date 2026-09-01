"""Provider-independent tests for the ACE-CT-inspired evaluator service."""

from __future__ import annotations

import copy
import json
import math

import pytest

from schemas.ace_ct import (
    ACE_CT_RUBRIC_V0_1,
    ACECTEvaluationFailure,
    ACECTEvaluationSuccess,
)
from services.ace_ct_evaluator_service import (
    MAX_MODEL_OUTPUT_CHARACTERS,
    ACECTEvaluatorService,
)
from services.ace_ct_transcript import project_ace_ct_transcript


class FakeAdapter:
    def __init__(self, response: object = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    async def generate_response(
        self,
        prompt: str,
        context: str = "",
        max_tokens: int = 500,
        temperature: float = 0.7,
    ) -> object:
        self.calls.append(
            {
                "prompt": prompt,
                "context": context,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        if self.error:
            raise self.error
        return self.response


def _transcript():
    return project_ace_ct_transcript(
        [
            {"turn_number": 1, "role": "assistant", "text": "I am worried."},
            {"turn_number": 2, "role": "user", "text": "Tell me more about that."},
            {"turn_number": 4, "role": "assistant", "text": "I fear what comes next."},
        ]
    )


def _valid_payload() -> dict:
    dimension_results = []
    scores_by_domain: dict[str, list[int]] = {}
    for index, spec in enumerate(ACE_CT_RUBRIC_V0_1.dimensions, start=1):
        score = ((index - 1) % 5) + 1
        dimension_results.append(
            {
                "dimension_id": spec.identifier.value,
                "domain": spec.domain.value,
                "score": score,
                "insufficient_evidence": False,
                "assessability": spec.assessability.value,
                "confidence": 0.8,
                "evidence_turn_numbers": [1, 2],
                "reasoning": "Concise evidence-based rationale.",
                "improvement_recommendation": "Use one more explicit communication behavior.",
                "modality_limitation_notes": list(spec.modality_limitations),
            }
        )
        scores_by_domain.setdefault(spec.domain.value, []).append(score)

    domain_scores = []
    for domain in ("respond", "listen", "speak", "general"):
        scores = scores_by_domain[domain]
        domain_scores.append(
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
        "dimension_results": dimension_results,
        "domain_scores": domain_scores,
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


async def _evaluate(payload: object, *, fenced: bool = False):
    response = json.dumps(payload)
    if fenced:
        response = f"```json\n{response}\n```"
    adapter = FakeAdapter(response=response)
    result = await ACECTEvaluatorService(adapter).evaluate(
        _transcript(),
        ACE_CT_RUBRIC_V0_1,
        allow_experimental_override=True,
    )
    return result, adapter


@pytest.mark.asyncio
async def test_valid_fake_response_returns_typed_success_at_temperature_zero() -> None:
    result, adapter = await _evaluate(_valid_payload())

    assert isinstance(result, ACECTEvaluationSuccess)
    assert result.status == "success"
    assert len(result.evaluation.dimension_results) == 11
    assert len(adapter.calls) == 1
    assert adapter.calls[0]["temperature"] == 0.0
    assert "BEGIN INTERLEAVED TRANSCRIPT" in adapter.calls[0]["prompt"]
    assert "transcript-only" in adapter.calls[0]["context"]


@pytest.mark.asyncio
@pytest.mark.parametrize("opening", ["```json", "```JSON", "```"])
async def test_optional_markdown_json_fence_is_removed(opening: str) -> None:
    adapter = FakeAdapter(response=f"{opening}\n{json.dumps(_valid_payload())}\n```")

    result = await ACECTEvaluatorService(adapter).evaluate(
        _transcript(),
        ACE_CT_RUBRIC_V0_1,
        allow_experimental_override=True,
    )

    assert isinstance(result, ACECTEvaluationSuccess)


@pytest.mark.asyncio
@pytest.mark.parametrize("response", ["not-json", "[1, 2, 3]", "```json\n{}"])
async def test_invalid_json_returns_typed_failure(response: str) -> None:
    adapter = FakeAdapter(response=response)

    result = await ACECTEvaluatorService(adapter).evaluate(
        _transcript(),
        ACE_CT_RUBRIC_V0_1,
        allow_experimental_override=True,
    )

    assert isinstance(result, ACECTEvaluationFailure)
    assert result.category == "invalid_json"
    assert response not in result.model_dump_json()


@pytest.mark.asyncio
async def test_adapter_exception_is_sanitized() -> None:
    private_value = "PRIVATE_TRANSCRIPT_OR_CREDENTIAL_VALUE_7391"
    adapter = FakeAdapter(error=RuntimeError(private_value))

    result = await ACECTEvaluatorService(adapter).evaluate(
        _transcript(),
        ACE_CT_RUBRIC_V0_1,
        allow_experimental_override=True,
    )

    assert isinstance(result, ACECTEvaluationFailure)
    assert result.category == "adapter_error"
    assert private_value not in result.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload["dimension_results"].pop(),
        lambda payload: payload["dimension_results"].__setitem__(
            -1, copy.deepcopy(payload["dimension_results"][0])
        ),
        lambda payload: payload["dimension_results"][0].__setitem__("score", 6),
        lambda payload: payload["dimension_results"][0].__setitem__("confidence", 2),
        lambda payload: payload["dimension_results"][0].__setitem__(
            "dimension_id", "unknown_dimension"
        ),
    ],
    ids=(
        "missing_dimension",
        "duplicate_dimension",
        "invalid_score",
        "invalid_confidence",
        "unknown_dimension",
    ),
)
async def test_schema_violations_return_invalid_output(mutation) -> None:
    payload = _valid_payload()
    mutation(payload)

    result, _ = await _evaluate(payload)

    assert isinstance(result, ACECTEvaluationFailure)
    assert result.category == "invalid_output"


@pytest.mark.asyncio
async def test_evidence_turn_must_exist_in_supplied_transcript() -> None:
    payload = _valid_payload()
    payload["dimension_results"][0]["evidence_turn_numbers"] = [1, 99]

    result, _ = await _evaluate(payload)

    assert isinstance(result, ACECTEvaluationFailure)
    assert result.category == "invalid_evidence_turn"


@pytest.mark.asyncio
async def test_excess_output_is_rejected_before_parsing() -> None:
    adapter = FakeAdapter(response="x" * (MAX_MODEL_OUTPUT_CHARACTERS + 1))

    result = await ACECTEvaluatorService(adapter).evaluate(
        _transcript(),
        ACE_CT_RUBRIC_V0_1,
        allow_experimental_override=True,
    )

    assert isinstance(result, ACECTEvaluationFailure)
    assert result.category == "excess_output"
    assert adapter.response[:100] not in result.diagnostic


@pytest.mark.asyncio
async def test_pending_rubric_is_rejected_before_adapter_call() -> None:
    adapter = FakeAdapter(response=json.dumps(_valid_payload()))

    result = await ACECTEvaluatorService(adapter).evaluate(
        _transcript(),
        ACE_CT_RUBRIC_V0_1,
    )

    assert isinstance(result, ACECTEvaluationFailure)
    assert result.category == "rubric_not_approved"
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_service_has_no_database_or_persistence_dependency() -> None:
    result, adapter = await _evaluate(_valid_payload())
    service = ACECTEvaluatorService(adapter)

    assert isinstance(result, ACECTEvaluationSuccess)
    assert not hasattr(service, "db")
    assert not hasattr(service, "repository")
    assert not hasattr(service, "session")


@pytest.mark.asyncio
async def test_logs_do_not_leak_transcript_raw_output_or_exception(caplog) -> None:
    private_text = "UNIQUE_PRIVATE_TRANSCRIPT_43879"
    transcript = project_ace_ct_transcript(
        [{"turn_number": 1, "role": "user", "text": private_text}]
    )
    adapter = FakeAdapter(error=RuntimeError(f"secret={private_text}"))

    result = await ACECTEvaluatorService(adapter).evaluate(
        transcript,
        ACE_CT_RUBRIC_V0_1,
        allow_experimental_override=True,
    )

    assert result.status == "failed"
    assert private_text not in caplog.text
    assert "secret=" not in caplog.text
    assert private_text not in result.model_dump_json()


@pytest.mark.asyncio
async def test_non_string_adapter_output_is_sanitized() -> None:
    adapter = FakeAdapter(response={"raw": "provider payload"})

    result = await ACECTEvaluatorService(adapter).evaluate(
        _transcript(),
        ACE_CT_RUBRIC_V0_1,
        allow_experimental_override=True,
    )

    assert isinstance(result, ACECTEvaluationFailure)
    assert result.category == "invalid_output"
    assert "provider payload" not in result.model_dump_json()
