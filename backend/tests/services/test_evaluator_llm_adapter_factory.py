"""Tests for evaluator-only model provider resolution."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import services.evaluator_llm_adapter_factory as factory


class FakeAdapter:
    def __init__(self, model_id: str | None = None):
        self.model_id = model_id


def test_fake_adapter_override_requires_no_settings_or_credentials(monkeypatch) -> None:
    def forbidden_settings():
        raise AssertionError("settings must not load for a fake adapter override")

    monkeypatch.setattr(factory, "get_settings", forbidden_settings)
    adapter = FakeAdapter()

    resolved = factory.resolve_evaluator_llm_adapter(
        "gemini",
        model_identifier="fake-model-v1",
        adapter_override=adapter,
    )

    assert resolved.provider == "gemini"
    assert resolved.model_identifier == "fake-model-v1"
    assert resolved.adapter is adapter


def test_fake_adapter_can_report_its_own_model_identifier(monkeypatch) -> None:
    monkeypatch.setattr(
        factory,
        "get_settings",
        lambda: (_ for _ in ()).throw(AssertionError("must not load settings")),
    )
    adapter = FakeAdapter(model_id="fake-reported-model")

    resolved = factory.resolve_evaluator_llm_adapter(
        "openai",
        adapter_override=adapter,
    )

    assert resolved.model_identifier == "fake-reported-model"


def test_configured_provider_model_identifiers_are_resolved(monkeypatch) -> None:
    monkeypatch.setattr(
        factory,
        "get_settings",
        lambda: SimpleNamespace(
            openai_model_id="gpt-configured",
            gemini_model_id="gemini-configured",
        ),
    )

    assert factory.get_configured_model_identifier("openai") == "gpt-configured"
    assert factory.get_configured_model_identifier("gemini") == "gemini-configured"


@pytest.mark.parametrize("provider", ["", "anthropic", "open ai", None])
def test_unknown_providers_are_rejected(provider) -> None:
    with pytest.raises(ValueError, match="Unsupported evaluator LLM provider"):
        factory.normalize_evaluator_llm_provider(provider)


@pytest.mark.parametrize(
    "model_identifier",
    ["", "contains space", "../unsafe", "x" * 201, "model?$"],
)
def test_unsafe_model_identifiers_are_rejected(model_identifier: str) -> None:
    with pytest.raises(ValueError, match="Model identifier"):
        factory.validate_model_identifier(model_identifier)


def test_real_openai_resolution_passes_safe_model_override(monkeypatch) -> None:
    import adapters.llm.openai_adapter as openai_module

    created: list[str | None] = []

    class StubOpenAIAdapter:
        def __init__(self, model_identifier=None):
            created.append(model_identifier)

    monkeypatch.setattr(openai_module, "OpenAIAdapter", StubOpenAIAdapter)

    resolved = factory.resolve_evaluator_llm_adapter(
        "openai",
        model_identifier="gpt-safe-1",
    )

    assert resolved.provider == "openai"
    assert resolved.model_identifier == "gpt-safe-1"
    assert created == ["gpt-safe-1"]


def test_real_gemini_resolution_passes_safe_model_override(monkeypatch) -> None:
    import adapters.llm.gemini_adapter as gemini_module

    created: list[str | None] = []

    class StubGeminiAdapter:
        def __init__(self, model_identifier=None):
            created.append(model_identifier)

    monkeypatch.setattr(gemini_module, "GeminiAdapter", StubGeminiAdapter)

    resolved = factory.resolve_evaluator_llm_adapter(
        "gemini",
        model_identifier="gemini-safe-1",
    )

    assert resolved.provider == "gemini"
    assert resolved.model_identifier == "gemini-safe-1"
    assert created == ["gemini-safe-1"]
