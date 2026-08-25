# This project was developed with assistance from AI tools.
"""Version-aware hybrid retrieval for the Chinese compliance knowledge base."""

import logging
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.inference.client import get_embeddings

from .ingestion import build_search_text

logger = logging.getLogger(__name__)

_TIER_BOOST = {1: 1.15, 2: 1.10, 3: 1.0}
_TIER_LABELS = {1: "全国监管政策", 2: "成都市地方规则", 3: "内部演示规则"}
_MIN_SIMILARITY = 0.3
_RRF_K = 60


def is_policy_active(
    effective_date: date | datetime | None,
    expires_at: date | datetime | None,
    as_of: date,
) -> bool:
    """Pure counterpart of the SQL validity filter, used by tests and diagnostics."""
    effective = effective_date.date() if isinstance(effective_date, datetime) else effective_date
    expires = expires_at.date() if isinstance(expires_at, datetime) else expires_at
    return (effective is None or effective <= as_of) and (expires is None or expires >= as_of)


@dataclass
class KBSearchResult:
    """A policy evidence chunk with independently verifiable citation fields."""

    chunk_text: str
    source_document: str
    section_ref: str | None
    tier: int
    tier_label: str
    similarity: float
    boosted_similarity: float
    effective_date: str | None
    issuer: str | None = None
    source_url: str | None = None
    jurisdiction: str = "national"
    source_type: str = "official"
    version: str | None = None
    published_date: str | None = None
    expires_at: str | None = None
    citation_id: str | None = None
    vector_rank: int | None = None
    keyword_rank: int | None = None
    keyword_score: float = 0.0
    rrf_score: float = 0.0


def _enum_value(value: Any, default: str) -> str:
    if value is None:
        return default
    if hasattr(value, "value"):
        return str(value.value)
    rendered = str(value)
    return default if rendered.startswith("<MagicMock") else rendered


def _optional_str(value: Any) -> str | None:
    if value is None or str(value).startswith("<MagicMock"):
        return None
    return str(value)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _result_from_row(row: Any, *, mode: str, rank: int) -> KBSearchResult:
    tier = int(row.tier)
    similarity = _float(getattr(row, "similarity", None))
    keyword_score = _float(getattr(row, "keyword_score", None))
    chunk_id = getattr(row, "id", rank)
    document_id = getattr(row, "document_id", None)
    citation_id = f"POL-{document_id or 'D'}-{chunk_id}"
    return KBSearchResult(
        chunk_text=row.chunk_text,
        source_document=row.title,
        section_ref=row.section_ref,
        tier=tier,
        tier_label=_TIER_LABELS.get(tier, f"第{tier}层政策"),
        similarity=similarity,
        boosted_similarity=similarity * _TIER_BOOST.get(tier, 1.0),
        effective_date=_optional_str(getattr(row, "effective_date", None)),
        issuer=_optional_str(getattr(row, "issuer", None)),
        source_url=_optional_str(getattr(row, "source_url", None)),
        jurisdiction=_enum_value(getattr(row, "jurisdiction", None), "national"),
        source_type=_enum_value(getattr(row, "source_type", None), "official"),
        version=_optional_str(getattr(row, "version", None)),
        published_date=_optional_str(getattr(row, "published_date", None)),
        expires_at=_optional_str(getattr(row, "expires_at", None)),
        citation_id=citation_id,
        vector_rank=rank if mode == "vector" else None,
        keyword_rank=rank if mode == "keyword" else None,
        keyword_score=keyword_score,
    )


def _filters_sql() -> str:
    return """
      AND (d.effective_date IS NULL OR d.effective_date <= :as_of)
      AND (d.expires_at IS NULL OR d.expires_at >= :as_of)
      AND (:jurisdiction IS NULL OR d.jurisdiction = :jurisdiction)
      AND (:source_type IS NULL OR d.source_type = :source_type)
    """


async def _vector_search(
    session: AsyncSession, query_vec: list[float], params: dict[str, Any]
) -> list[KBSearchResult]:
    sql = text(
        """
        SELECT c.id, c.document_id, c.chunk_text, c.section_ref, d.title, d.tier,
               d.issuer, d.source_url, d.jurisdiction, d.source_type,
               d.version, d.published_date, d.effective_date, d.expires_at,
               1 - (c.embedding <=> :query_vec) AS similarity
        FROM kb_chunks c
        JOIN kb_documents d ON c.document_id = d.id
        WHERE c.embedding IS NOT NULL
        """
        + _filters_sql()
        + " ORDER BY c.embedding <=> :query_vec LIMIT :fetch_limit"
    )
    result = await session.execute(sql, {**params, "query_vec": str(query_vec)})
    rows = result.fetchall()
    return [
        _result_from_row(row, mode="vector", rank=rank)
        for rank, row in enumerate(rows, 1)
        if _float(getattr(row, "similarity", None)) >= _MIN_SIMILARITY
    ]


def _keyword_tsquery(query: str) -> str:
    tokens = build_search_text(query).split()
    safe = [token for token in tokens if token.replace(".", "").replace("%", "").isalnum()]
    return " | ".join(safe[:32])


async def _keyword_search(
    session: AsyncSession, query: str, params: dict[str, Any]
) -> list[KBSearchResult]:
    tsquery = _keyword_tsquery(query)
    if not tsquery:
        return []
    sql = text(
        """
        SELECT c.id, c.document_id, c.chunk_text, c.section_ref, d.title, d.tier,
               d.issuer, d.source_url, d.jurisdiction, d.source_type,
               d.version, d.published_date, d.effective_date, d.expires_at,
               ts_rank_cd(
                   to_tsvector('simple', c.search_text),
                   to_tsquery('simple', :tsquery)
               ) AS keyword_score
        FROM kb_chunks c
        JOIN kb_documents d ON c.document_id = d.id
        WHERE to_tsvector('simple', c.search_text) @@ to_tsquery('simple', :tsquery)
        """
        + _filters_sql()
        + " ORDER BY keyword_score DESC LIMIT :fetch_limit"
    )
    result = await session.execute(sql, {**params, "tsquery": tsquery})
    return [
        _result_from_row(row, mode="keyword", rank=rank)
        for rank, row in enumerate(result.fetchall(), 1)
    ]


def reciprocal_rank_fusion(
    vector_results: list[KBSearchResult], keyword_results: list[KBSearchResult]
) -> list[KBSearchResult]:
    """Fuse rankings without requiring vector and lexical scores to share a scale."""
    fused: dict[tuple[str, str | None, str], KBSearchResult] = {}
    scores: dict[tuple[str, str | None, str], float] = {}

    for results, rank_field in (
        (vector_results, "vector_rank"),
        (keyword_results, "keyword_rank"),
    ):
        for result in results:
            key = (result.source_document, result.section_ref, result.chunk_text)
            rank = getattr(result, rank_field)
            if rank is None:
                continue
            score = _TIER_BOOST.get(result.tier, 1.0) / (_RRF_K + rank)
            scores[key] = scores.get(key, 0.0) + score
            if key not in fused:
                fused[key] = replace(result)
            else:
                current = fused[key]
                if result.vector_rank is not None:
                    current.vector_rank = result.vector_rank
                    current.similarity = result.similarity
                    current.boosted_similarity = result.boosted_similarity
                if result.keyword_rank is not None:
                    current.keyword_rank = result.keyword_rank
                    current.keyword_score = result.keyword_score

    for key, result in fused.items():
        result.rrf_score = scores[key]
    return sorted(fused.values(), key=lambda item: item.rrf_score, reverse=True)


async def search_kb(
    session: AsyncSession,
    query: str,
    top_k: int = 5,
    *,
    as_of: date | None = None,
    jurisdiction: str | None = None,
    source_type: str | None = None,
) -> list[KBSearchResult]:
    """Run vector and Chinese lexical retrieval, then combine them with RRF."""
    params = {
        "fetch_limit": top_k * 3,
        "as_of": as_of or date.today(),
        "jurisdiction": jurisdiction,
        "source_type": source_type,
    }
    vector_results: list[KBSearchResult] = []
    try:
        embeddings = await get_embeddings([query])
        vector_results = await _vector_search(session, embeddings[0], params)
    except Exception:
        logger.warning(
            "Vector policy retrieval failed; continuing with lexical search", exc_info=True
        )

    try:
        keyword_results = await _keyword_search(session, query, params)
    except Exception:
        logger.warning(
            "Lexical policy retrieval failed; continuing with vector search", exc_info=True
        )
        keyword_results = []

    return reciprocal_rank_fusion(vector_results, keyword_results)[:top_k]
