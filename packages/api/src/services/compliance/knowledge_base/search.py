# This project was developed with assistance from AI tools.
"""Compliance KB vector search with tier-based boosting.

Performs cosine similarity search via pgvector, applies tier boost
factors to prioritize federal regulations over internal policies,
and returns results with citation metadata.
"""

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.inference.client import get_embeddings

logger = logging.getLogger(__name__)

# Tier boost factors: federal > agency > internal
_TIER_BOOST = {1: 1.5, 2: 1.2, 3: 1.0}
_TIER_LABELS = {1: "Federal Regulation", 2: "Agency Guideline", 3: "Internal Policy"}
_MIN_SIMILARITY = 0.3


@dataclass
class KBSearchResult:
    """A single compliance KB search result with citation metadata."""

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


async def search_kb(
    session: AsyncSession,
    query: str,
    top_k: int = 5,
    *,
    as_of: date | None = None,
    jurisdiction: str | None = None,
    source_type: str | None = None,
) -> list[KBSearchResult]:
    """Search the compliance KB using vector similarity with tier boosting.

    Args:
        session: Database session.
        query: Search query text.
        top_k: Number of results to return after boosting.

    Returns:
        List of KBSearchResult ordered by boosted similarity (descending).
    """
    as_of = as_of or date.today()

    # Get query embedding
    try:
        embeddings = await get_embeddings([query])
        query_vec = embeddings[0]
    except Exception:
        logger.warning("Failed to get query embedding, returning empty results")
        return []

    # Fetch top_k * 3 candidates from DB, apply boost, re-sort, truncate
    fetch_limit = top_k * 3

    sql = text("""
        SELECT c.id, c.chunk_text, c.section_ref, d.title, d.tier,
               d.issuer, d.source_url, d.jurisdiction, d.source_type,
               d.version, d.published_date, d.effective_date, d.expires_at,
               1 - (c.embedding <=> :query_vec) AS similarity
        FROM kb_chunks c
        JOIN kb_documents d ON c.document_id = d.id
        WHERE c.embedding IS NOT NULL
          AND (d.effective_date IS NULL OR d.effective_date <= :as_of)
          AND (d.expires_at IS NULL OR d.expires_at >= :as_of)
          AND (:jurisdiction IS NULL OR d.jurisdiction = :jurisdiction)
          AND (:source_type IS NULL OR d.source_type = :source_type)
        ORDER BY c.embedding <=> :query_vec
        LIMIT :fetch_limit
    """)

    result = await session.execute(
        sql,
        {
            "query_vec": str(query_vec),
            "fetch_limit": fetch_limit,
            "as_of": as_of,
            "jurisdiction": jurisdiction,
            "source_type": source_type,
        },
    )
    rows = result.fetchall()

    # Apply tier boost and filter by minimum similarity
    results: list[KBSearchResult] = []
    for row in rows:
        similarity = float(row.similarity)
        if similarity < _MIN_SIMILARITY:
            continue

        tier = row.tier
        boost = _TIER_BOOST.get(tier, 1.0)
        boosted = similarity * boost

        results.append(
            KBSearchResult(
                chunk_text=row.chunk_text,
                source_document=row.title,
                section_ref=row.section_ref,
                tier=tier,
                tier_label=_TIER_LABELS.get(tier, f"Tier {tier}"),
                similarity=similarity,
                boosted_similarity=boosted,
                issuer=row.issuer,
                source_url=row.source_url,
                jurisdiction=(
                    row.jurisdiction.value
                    if hasattr(row.jurisdiction, "value")
                    else str(row.jurisdiction)
                ),
                source_type=(
                    row.source_type.value
                    if hasattr(row.source_type, "value")
                    else str(row.source_type)
                ),
                version=row.version,
                published_date=str(row.published_date) if row.published_date else None,
                effective_date=str(row.effective_date) if row.effective_date else None,
                expires_at=str(row.expires_at) if row.expires_at else None,
            )
        )

    # Sort by boosted similarity descending, truncate to top_k
    results.sort(key=lambda r: r.boosted_similarity, reverse=True)
    return results[:top_k]
