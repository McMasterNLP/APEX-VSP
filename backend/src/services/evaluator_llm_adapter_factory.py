"""Provider resolver for evaluator-only model adapters."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from config.settings import get_settings

EvaluatorLLMProvider = Literal["openai", "gemini"]
SUPPORTED_EVALUATOR_LLM_PROVIDERS = ("openai", "gemini")
_MODEL_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}")


@dataclass(frozen=True)
class ResolvedEvaluatorLLMAdapter:
    """Adapter plus allowlisted provenance resolved from one provider choice."""

    provider: EvaluatorLLMProvider
    model_identifier: str
    adapter: Any


def normalize_evaluator_llm_provider(provider: str) -> EvaluatorLLMProvider:
    value = str(provider).strip().lower()
    if value not in SUPPORTED_EVALUATOR_LLM_PROVIDERS:
        raise ValueError(
            f"Unsupported evaluator LLM provider '{value}'. Expected openai or gemini."
        )
    return value  # type: ignore[return-value]


def validate_model_identifier(model_identifier: str) -> str:
    value = str(model_identifier).strip()
    if not _MODEL_IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError("Model identifier must be 1-200 safe identifier characters.")
    return value


def get_configured_model_identifier(
    provider: str,
    *,
    model_identifier: str | None = None,
) -> str:
    """Resolve a safe explicit or configured model identifier."""

    normalized_provider = normalize_evaluator_llm_provider(provider)
    if model_identifier is not None:
        return validate_model_identifier(model_identifier)
    settings = get_settings()
    configured = (
        settings.openai_model_id if normalized_provider == "openai" else settings.gemini_model_id
    )
    return validate_model_identifier(configured)


def resolve_evaluator_llm_adapter(
    provider: str,
    *,
    model_identifier: str | None = None,
    adapter_override: Any | None = None,
) -> ResolvedEvaluatorLLMAdapter:
    """Create a provider adapter, or use a test override without reading credentials."""

    normalized_provider = normalize_evaluator_llm_provider(provider)
    if adapter_override is not None:
        override_model = model_identifier or getattr(adapter_override, "model_id", None)
        if override_model is None:
            raise ValueError("A fake adapter override requires an explicit model identifier.")
        return ResolvedEvaluatorLLMAdapter(
            provider=normalized_provider,
            model_identifier=validate_model_identifier(override_model),
            adapter=adapter_override,
        )

    resolved_model = get_configured_model_identifier(
        normalized_provider,
        model_identifier=model_identifier,
    )
    if normalized_provider == "openai":
        from adapters.llm.openai_adapter import OpenAIAdapter

        adapter = OpenAIAdapter(model_identifier=resolved_model)
    else:
        from adapters.llm.gemini_adapter import GeminiAdapter

        adapter = GeminiAdapter(model_identifier=resolved_model)
    return ResolvedEvaluatorLLMAdapter(
        provider=normalized_provider,
        model_identifier=resolved_model,
        adapter=adapter,
    )
