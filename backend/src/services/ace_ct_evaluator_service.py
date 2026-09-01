"""Provider-independent execution for experimental ACE-CT-inspired evaluation."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from config.logging import get_logger
from schemas.ace_ct import (
    ACECTEvaluationFailure,
    ACECTEvaluationResult,
    ACECTEvaluationServiceResult,
    ACECTEvaluationSuccess,
    ACECTRubricApprovalError,
    ACECTRubricSpec,
    ACECTTranscript,
    require_ace_ct_rubric_approval,
)
from services.ace_ct_prompt import build_ace_ct_prompt

logger = get_logger(__name__)

MAX_MODEL_OUTPUT_CHARACTERS = 50_000
MODEL_MAX_TOKENS = 6_000

_DIAGNOSTICS = {
    "rubric_not_approved": "Rubric approval policy refused evaluation.",
    "adapter_error": "The configured model adapter failed.",
    "invalid_json": "Model output was not one strict JSON object.",
    "invalid_output": "Model output did not satisfy the strict evaluation schema.",
    "invalid_evidence_turn": "Model output cited a turn outside the supplied transcript.",
    "excess_output": "Model output exceeded the configured response limit.",
}


class ACECTEvaluatorService:
    """Evaluate a projected transcript without persistence or provider construction."""

    def __init__(self, llm_adapter: Any):
        self._llm_adapter = llm_adapter

    @staticmethod
    def _failure(category: str) -> ACECTEvaluationFailure:
        logger.warning("ACE-CT-inspired evaluation failed category=%s", category)
        return ACECTEvaluationFailure(
            category=category,
            diagnostic=_DIAGNOSTICS[category],
        )

    @staticmethod
    def _strip_optional_json_fence(response: str) -> str:
        stripped = response.strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            return stripped
        opening = lines[0].strip().lower()
        if opening not in {"```", "```json"}:
            return stripped
        return "\n".join(lines[1:-1]).strip()

    async def evaluate(
        self,
        transcript: ACECTTranscript,
        rubric: ACECTRubricSpec,
        *,
        allow_experimental_override: bool = False,
    ) -> ACECTEvaluationServiceResult:
        """Call the injected adapter once and strictly validate its JSON response."""

        try:
            require_ace_ct_rubric_approval(
                rubric,
                allow_experimental_override=allow_experimental_override,
            )
        except ACECTRubricApprovalError:
            return self._failure("rubric_not_approved")

        prompt = build_ace_ct_prompt(transcript, rubric)
        try:
            raw_response = await self._llm_adapter.generate_response(
                prompt.user_message,
                context=prompt.system_message,
                max_tokens=MODEL_MAX_TOKENS,
                temperature=0.0,
            )
        except Exception:
            return self._failure("adapter_error")

        if not isinstance(raw_response, str):
            return self._failure("invalid_output")
        if len(raw_response) > MAX_MODEL_OUTPUT_CHARACTERS:
            return self._failure("excess_output")

        json_text = self._strip_optional_json_fence(raw_response)
        try:
            payload = json.loads(json_text)
        except (json.JSONDecodeError, TypeError):
            return self._failure("invalid_json")
        if not isinstance(payload, dict):
            return self._failure("invalid_json")

        try:
            evaluation = ACECTEvaluationResult.model_validate(payload)
        except ValidationError:
            return self._failure("invalid_output")

        valid_turn_numbers = set(transcript.turn_numbers)
        if any(
            turn_number not in valid_turn_numbers
            for result in evaluation.dimension_results
            for turn_number in result.evidence_turn_numbers
        ):
            return self._failure("invalid_evidence_turn")

        return ACECTEvaluationSuccess(evaluation=evaluation)
