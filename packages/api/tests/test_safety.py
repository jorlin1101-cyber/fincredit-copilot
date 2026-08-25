# This project was developed with assistance from AI tools.
"""Tests for the current NeMo Guardrails safety adapter."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.config import settings
from src.inference.safety import NeMoGuardrailsChecker, SafetyChecker, get_safety_checker


@pytest.fixture(autouse=True)
def _clear_checker_cache():
    import src.inference.safety as safety_mod

    safety_mod._checker_instance = None
    yield
    safety_mod._checker_instance = None


def _response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


@pytest.mark.asyncio
async def test_allowed_response_is_safe():
    checker = NeMoGuardrailsChecker(endpoint="http://nemo")
    checker._client.post = AsyncMock(return_value=_response({"status": "allowed"}))

    result = await checker.check_input("请介绍住房贷款流程")

    assert result.is_safe is True
    assert result.violation_categories == []


@pytest.mark.asyncio
async def test_blocked_response_includes_activated_rails():
    checker = NeMoGuardrailsChecker(endpoint="http://nemo")
    checker._client.post = AsyncMock(
        return_value=_response(
            {
                "status": "blocked",
                "guardrails_data": {"log": {"activated_rails": ["pii_leak", "jailbreak"]}},
            }
        )
    )

    result = await checker.check_input("unsafe")

    assert result.is_safe is False
    assert result.violation_categories == ["pii_leak", "jailbreak"]
    assert "pii_leak" in result.explanation


@pytest.mark.asyncio
async def test_input_check_fails_closed_on_transport_error():
    checker = NeMoGuardrailsChecker(endpoint="http://nemo")
    checker._client.post = AsyncMock(side_effect=ConnectionError("unreachable"))

    result = await checker.check_input("anything")

    assert result.is_safe is False
    assert result.explanation == "Safety check unavailable"


@pytest.mark.asyncio
async def test_output_check_fails_closed_on_transport_error():
    checker = NeMoGuardrailsChecker(endpoint="http://nemo")
    checker._client.post = AsyncMock(side_effect=TimeoutError("timeout"))

    result = await checker.check_output("问题", "回答")

    assert result.is_safe is False
    assert result.explanation == "Safety check unavailable"


@pytest.mark.asyncio
async def test_input_payload_contains_user_message():
    checker = NeMoGuardrailsChecker(endpoint="http://nemo/")
    checker._client.post = AsyncMock(return_value=_response({"status": "allowed"}))

    await checker.check_input("我的材料需要人工复核")

    call = checker._client.post.await_args
    assert call.args[0] == "http://nemo/v1/guardrail/checks"
    assert call.kwargs["json"]["messages"] == [
        {"role": "user", "content": "我的材料需要人工复核"}
    ]


@pytest.mark.asyncio
async def test_output_payload_contains_both_messages():
    checker = NeMoGuardrailsChecker(endpoint="http://nemo")
    checker._client.post = AsyncMock(return_value=_response({"status": "allowed"}))

    await checker.check_output("问题", "回答")

    messages = checker._client.post.await_args.kwargs["json"]["messages"]
    assert messages == [
        {"role": "user", "content": "问题"},
        {"role": "assistant", "content": "回答"},
    ]


def test_legacy_safety_checker_name_is_compatible():
    assert SafetyChecker is NeMoGuardrailsChecker


def test_get_safety_checker_returns_none_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "NEMO_GUARDRAILS_ENDPOINT", None)
    assert get_safety_checker() is None


def test_get_safety_checker_returns_cached_instance(monkeypatch):
    monkeypatch.setattr(settings, "NEMO_GUARDRAILS_ENDPOINT", "http://nemo")

    first = get_safety_checker()
    second = get_safety_checker()

    assert isinstance(first, NeMoGuardrailsChecker)
    assert first is second
