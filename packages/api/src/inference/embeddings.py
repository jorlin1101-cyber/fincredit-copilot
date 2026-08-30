# This project was developed with assistance from AI tools.
"""Embedding provider abstraction.

Supports two providers:
- ``local``: in-process inference via sentence-transformers (no external service needed).
- ``openai_compatible``: remote call to any OpenAI-compatible ``/v1/embeddings`` endpoint.

The active provider is determined by the ``embedding`` model config in
``config/models.yaml``.  Set ``provider: local`` to run the model in-process,
or ``provider: openai_compatible`` to delegate to a remote server.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np

from .config import get_model_config

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingDimensionError(ValueError):
    """Raised before invalid-width vectors can reach pgvector."""


def validate_embedding_dimensions(
    vectors: list[list[float]], expected_dimensions: int
) -> list[list[float]]:
    """Reject provider responses that do not match the database vector width."""
    for index, vector in enumerate(vectors):
        actual = len(vector)
        if actual != expected_dimensions:
            raise EmbeddingDimensionError(
                "Embedding dimension mismatch at vector "
                f"{index}: expected {expected_dimensions}, received {actual}. "
                "Check EMBEDDING_MODEL and EMBEDDING_DIMENSIONS before ingestion."
            )
    return vectors


class EmbeddingProvider(ABC):
    """Common interface for embedding providers."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for *texts*."""


class LocalEmbeddingProvider(EmbeddingProvider):
    """In-process embedding using sentence-transformers.

    The model is loaded lazily on first call and cached for the process
    lifetime.  CPU inference is used by default; nomic-embed-text-v1.5
    (~270 MB) loads in ~2 s and embeds a single query in < 50 ms on CPU.
    """

    def __init__(self, model_name: str, dimensions: int = 768) -> None:
        self._model_name = model_name
        self._dimensions = dimensions
        self._model: "SentenceTransformer | None" = None

    def _load_model(self) -> "SentenceTransformer":
        if self._model is None:
            # Keep the large torch/transformers dependency out of the normal
            # remote-embedding path. It is only needed for provider=local.
            from sentence_transformers import SentenceTransformer

            logger.info("Loading local embedding model: %s", self._model_name)
            self._model = SentenceTransformer(self._model_name, trust_remote_code=True)
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        # sentence-transformers returns numpy ndarray
        vectors = model.encode(texts, normalize_embeddings=True)
        if isinstance(vectors, np.ndarray):
            result = vectors.tolist()
        else:
            result = [v.tolist() if hasattr(v, "tolist") else list(v) for v in vectors]
        return validate_embedding_dimensions(result, self._dimensions)


class RemoteEmbeddingProvider(EmbeddingProvider):
    """Embedding via an OpenAI-compatible ``/v1/embeddings`` endpoint."""

    def __init__(
        self,
        endpoint: str,
        model_name: str,
        api_key: str = "not-needed",
        dimensions: int = 768,
        batch_size: int = 10,
    ) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            base_url=endpoint,
            api_key=api_key,
            max_retries=1,
            timeout=60.0,
        )
        self._model_name = model_name
        self._dimensions = dimensions
        self._batch_size = batch_size

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            response = await self._client.embeddings.create(
                model=self._model_name,
                input=texts[start : start + self._batch_size],
                dimensions=self._dimensions,
                encoding_format="float",
            )
            vectors.extend(item.embedding for item in response.data)
        return validate_embedding_dimensions(vectors, self._dimensions)


# --- singleton management ---

_provider: EmbeddingProvider | None = None


def _build_provider() -> EmbeddingProvider:
    """Construct the provider from the current ``embedding`` model config."""
    cfg = get_model_config("embedding")
    provider_type = cfg.get("provider", "openai_compatible")

    if provider_type == "local":
        return LocalEmbeddingProvider(
            model_name=cfg["model_name"],
            dimensions=int(cfg.get("dimensions", 768)),
        )

    # Default: openai_compatible (covers vLLM, LMStudio, TEI, etc.)
    # Fall back to LLM_BASE_URL / LLM_API_KEY when embedding-specific vars
    # are not set (keeps the common single-endpoint dev setup working).
    endpoint = cfg.get("endpoint") or os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    api_key = cfg.get("api_key") or os.environ.get("LLM_API_KEY", "not-needed")
    return RemoteEmbeddingProvider(
        endpoint=endpoint,
        model_name=cfg["model_name"],
        api_key=api_key,
        dimensions=int(cfg.get("dimensions", 768)),
    )


def get_embedding_provider() -> EmbeddingProvider:
    """Return the cached embedding provider, building it on first access."""
    global _provider  # noqa: PLW0603
    if _provider is None:
        _provider = _build_provider()
    return _provider


def reset_embedding_provider() -> None:
    """Discard the cached provider (e.g. after config reload)."""
    global _provider  # noqa: PLW0603
    _provider = None
