"""Model-aware request params for OpenAIAdapter (no real OpenAI calls)."""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("database_url", "sqlite:///./test_openai_adapter_params.db")
os.environ.setdefault("secret_key", "test-secret")
os.environ.setdefault("supabase_jwt_secret", "test-supabase-jwt")
os.environ.setdefault("gemini_api_key", "test-gemini-key")
os.environ.setdefault("openai_api_key", "test-openai-key")

from adapters.llm.openai_adapter import OpenAIAdapter  # noqa: E402


def _adapter(model: str, effort: str = "none") -> OpenAIAdapter:
    adapter = OpenAIAdapter(model_identifier=model)
    adapter.reasoning_effort = effort
    return adapter


@pytest.mark.parametrize("model", ["gpt-4o-mini", "gpt-4.1", "gpt-4", "gpt-3.5-turbo"])
def test_legacy_chat_models_use_max_tokens_and_temperature(model):
    assert _adapter(model, effort="medium")._completion_params(300, 0.4) == {
        "max_tokens": 300,
        "temperature": 0.4,
    }


def test_luna_with_effort_none_keeps_temperature():
    assert _adapter("gpt-6-luna", "none")._completion_params(300, 0.4) == {
        "max_completion_tokens": 300,
        "reasoning_effort": "none",
        "temperature": 0.4,
    }


def test_luna_with_effort_medium_omits_temperature():
    assert _adapter("gpt-6-luna", "medium")._completion_params(500, 0.0) == {
        "max_completion_tokens": 500,
        "reasoning_effort": "medium",
    }


@pytest.mark.parametrize("model", ["o3", "o4-mini", "o1"])
def test_o_series_sends_only_max_completion_tokens(model):
    assert _adapter(model, "none")._completion_params(200, 0.3) == {
        "max_completion_tokens": 200,
    }


def test_default_settings_target_luna_with_effort_none():
    adapter = OpenAIAdapter()
    assert adapter.model_id == "gpt-6-luna"
    assert adapter.reasoning_effort == "none"


def _mock_client(adapter: OpenAIAdapter, content: str) -> AsyncMock:
    create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )
    )
    adapter.client = MagicMock()
    adapter.client.chat.completions.create = create
    return create


@pytest.mark.asyncio
async def test_all_three_calls_send_luna_params():
    adapter = _adapter("gpt-6-luna", "none")
    create = _mock_client(adapter, '{"empathy_score": 7}')

    await adapter.generate_response("hi", context="ctx", max_tokens=123, temperature=0.0)
    await adapter.generate_patient_response("case", [{"role": "user", "content": "Hello"}], "S")
    await adapter.analyze_turn("How are you feeling?", [])

    sent = [
        {k: v for k, v in call.kwargs.items() if k not in ("model", "messages")}
        for call in create.await_args_list
    ]
    assert sent == [
        {"max_completion_tokens": 123, "reasoning_effort": "none", "temperature": 0.0},
        {"max_completion_tokens": 300, "reasoning_effort": "none", "temperature": 0.4},
        {"max_completion_tokens": 200, "reasoning_effort": "none", "temperature": 0.3},
    ]
    assert all(call.kwargs["model"] == "gpt-6-luna" for call in create.await_args_list)


@pytest.mark.asyncio
async def test_all_three_calls_keep_legacy_params_for_rollback_model():
    adapter = _adapter("gpt-4o-mini", "none")
    create = _mock_client(adapter, '{"empathy_score": 7}')

    await adapter.generate_response("hi", max_tokens=50, temperature=0.7)
    await adapter.generate_patient_response("case", [{"role": "user", "content": "Hello"}], "S")
    await adapter.analyze_turn("How are you feeling?", [])

    sent = [
        {k: v for k, v in call.kwargs.items() if k not in ("model", "messages")}
        for call in create.await_args_list
    ]
    assert sent == [
        {"max_tokens": 50, "temperature": 0.7},
        {"max_tokens": 300, "temperature": 0.4},
        {"max_tokens": 200, "temperature": 0.3},
    ]
