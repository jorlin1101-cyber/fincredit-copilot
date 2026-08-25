# This project was developed with assistance from AI tools.
"""Thin OpenAI-compatible LLM client.

Wraps the openai Python SDK with configurable base_url so it works
against any OpenAI-compatible endpoint (OpenAI, vLLM, LlamaStack, etc.).
"""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)

from .config import get_model_config

logger = logging.getLogger(__name__)

# Per-tier client cache (avoids re-creating HTTP connections)
_clients: dict[str, AsyncOpenAI] = {}


class InferenceError(RuntimeError):
    """Sanitized provider failure suitable for API responses and fault drills."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        retryable: bool,
        model: str,
        status_code: int | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.model = model
        self.status_code = status_code
        self.trace_id = trace_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "retryable": self.retryable,
            "model": self.model,
            "status_code": self.status_code,
            "trace_id": self.trace_id,
        }


@dataclass(frozen=True)
class CompletionResult:
    content: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


def _get_client(tier: str) -> AsyncOpenAI:
    """Return a cached AsyncOpenAI client for the given model tier."""
    if tier not in _clients:
        model_cfg = get_model_config(tier)
        _clients[tier] = AsyncOpenAI(
            base_url=model_cfg["endpoint"],
            api_key=model_cfg.get("api_key", "not-needed"),
            max_retries=1,
            timeout=60.0,
        )
    return _clients[tier]


def clear_client_cache() -> None:
    """Clear cached clients (useful after config reload)."""
    _clients.clear()


async def get_completion(
    messages: list[dict[str, str]],
    tier: str = "llm",
    trace_id: str | None = None,
    **kwargs: Any,
) -> str:
    """Get a non-streaming completion from the specified model tier."""
    result = await get_completion_result(messages, tier=tier, trace_id=trace_id, **kwargs)
    return result.content


async def get_completion_result(
    messages: list[dict[str, str]],
    tier: str = "llm",
    trace_id: str | None = None,
    **kwargs: Any,
) -> CompletionResult:
    """Get content plus actual provider token usage when available."""
    client = _get_client(tier)
    model_cfg = get_model_config(tier)
    model_name = str(model_cfg["model_name"])
    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            **kwargs,
        )
    except RateLimitError as exc:
        raise InferenceError(
            "模型服务触发限流，请稍后重试或转人工处理。",
            code="MODEL_RATE_LIMITED",
            retryable=True,
            model=model_name,
            status_code=429,
            trace_id=trace_id,
        ) from exc
    except APITimeoutError as exc:
        raise InferenceError(
            "模型服务请求超时，有限重试后仍未恢复。",
            code="MODEL_TIMEOUT",
            retryable=True,
            model=model_name,
            trace_id=trace_id,
        ) from exc
    except APIConnectionError as exc:
        raise InferenceError(
            "无法连接模型服务。",
            code="MODEL_UNAVAILABLE",
            retryable=True,
            model=model_name,
            trace_id=trace_id,
        ) from exc
    except APIStatusError as exc:
        raise InferenceError(
            "模型服务返回异常状态。",
            code="MODEL_PROVIDER_ERROR",
            retryable=exc.status_code >= 500,
            model=model_name,
            status_code=exc.status_code,
            trace_id=trace_id,
        ) from exc
    usage = response.usage
    return CompletionResult(
        content=response.choices[0].message.content or "",
        model=model_name,
        input_tokens=usage.prompt_tokens if usage else None,
        output_tokens=usage.completion_tokens if usage else None,
    )


async def get_embeddings(texts: list[str], tier: str = "embedding") -> list[list[float]]:
    """Get embeddings for a list of texts from the configured provider.

    The provider (local sentence-transformers or remote OpenAI-compatible)
    is determined by the ``embedding`` model config in ``config/models.yaml``.
    """
    from .embeddings import get_embedding_provider

    provider = get_embedding_provider()
    return await provider.embed(texts)


async def get_streaming_completion(
    messages: list[dict[str, str]],
    tier: str = "llm",
    **kwargs: Any,
) -> AsyncIterator[str]:
    """Get a streaming completion, yielding content deltas."""
    client = _get_client(tier)
    model_cfg = get_model_config(tier)

    stream = await client.chat.completions.create(
        model=model_cfg["model_name"],
        messages=messages,
        stream=True,
        **kwargs,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
