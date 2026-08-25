# This project was developed with assistance from AI tools.
"""Fault drills for bounded Qwen provider failures and policy expiry."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from openai import APITimeoutError, RateLimitError

from src.inference.client import InferenceError, get_completion, get_completion_result
from src.services.compliance.knowledge_base.search import is_policy_active


def _client_with_error(error):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=error)
    return client


@pytest.mark.asyncio
async def test_qwen_429_becomes_structured_retryable_error_with_trace(monkeypatch):
    request = httpx.Request("POST", "https://dashscope.example/v1/chat/completions")
    response = httpx.Response(429, request=request)
    error = RateLimitError("rate limited", response=response, body={})
    import src.inference.client as mod

    monkeypatch.setattr(mod, "_get_client", lambda _tier: _client_with_error(error))
    monkeypatch.setattr(mod, "get_model_config", lambda _tier: {"model_name": "qwen-test"})

    with pytest.raises(InferenceError) as captured:
        await get_completion([], trace_id="trace-429")

    payload = captured.value.to_dict()
    assert payload["code"] == "MODEL_RATE_LIMITED"
    assert payload["retryable"] is True
    assert payload["status_code"] == 429
    assert payload["trace_id"] == "trace-429"


@pytest.mark.asyncio
async def test_qwen_timeout_becomes_structured_error(monkeypatch):
    request = httpx.Request("POST", "https://dashscope.example/v1/chat/completions")
    import src.inference.client as mod

    monkeypatch.setattr(
        mod,
        "_get_client",
        lambda _tier: _client_with_error(APITimeoutError(request=request)),
    )
    monkeypatch.setattr(mod, "get_model_config", lambda _tier: {"model_name": "qwen-test"})

    with pytest.raises(InferenceError) as captured:
        await get_completion([], trace_id="trace-timeout")

    assert captured.value.code == "MODEL_TIMEOUT"
    assert captured.value.trace_id == "trace-timeout"


@pytest.mark.asyncio
async def test_completion_result_exposes_actual_provider_token_usage(monkeypatch):
    response = MagicMock()
    response.choices[0].message.content = "完成"
    response.usage.prompt_tokens = 20
    response.usage.completion_tokens = 5
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)
    import src.inference.client as mod

    monkeypatch.setattr(mod, "_get_client", lambda _tier: client)
    monkeypatch.setattr(mod, "get_model_config", lambda _tier: {"model_name": "qwen-test"})

    result = await get_completion_result([])
    assert result.content == "完成"
    assert result.input_tokens == 20
    assert result.output_tokens == 5


def test_expired_policy_is_excluded_on_next_day():
    assert is_policy_active(date(2023, 10, 20), date(2026, 3, 24), date(2026, 3, 24))
    assert not is_policy_active(date(2023, 10, 20), date(2026, 3, 24), date(2026, 3, 25))
