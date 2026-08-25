# This project was developed with assistance from AI tools.
"""Tests for version-aware Chinese hybrid policy retrieval."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.compliance.knowledge_base.search import (
    KBSearchResult,
    reciprocal_rank_fusion,
    search_kb,
)


def _make_row(
    chunk_text: str,
    title: str,
    section_ref: str | None,
    tier: int,
    *,
    row_id: int,
    similarity: float = 0.0,
    keyword_score: float = 0.0,
):
    row = MagicMock()
    row.id = row_id
    row.document_id = row_id + 100
    row.chunk_text = chunk_text
    row.title = title
    row.section_ref = section_ref
    row.tier = tier
    row.effective_date = "2026-03-25"
    row.similarity = similarity
    row.keyword_score = keyword_score
    row.issuer = "测试发布机构"
    row.source_url = f"https://example.gov.cn/{row_id}"
    row.jurisdiction = "chengdu" if tier == 2 else "national"
    row.source_type = "official"
    row.version = "2026-v1"
    row.published_date = "2026-03-24"
    row.expires_at = None
    return row


def _db_result(rows):
    result = MagicMock()
    result.fetchall.return_value = rows
    return result


def _search_result(name: str, tier: int, vector_rank=None, keyword_rank=None):
    return KBSearchResult(
        chunk_text=f"{name}正文",
        source_document=name,
        section_ref="测试条款",
        tier=tier,
        tier_label="测试层级",
        similarity=0.8,
        boosted_similarity=0.8,
        effective_date="2026-03-25",
        vector_rank=vector_rank,
        keyword_rank=keyword_rank,
    )


def test_rrf_rewards_evidence_found_by_both_retrievers():
    shared_vector = _search_result("共同证据", 2, vector_rank=2)
    shared_keyword = _search_result("共同证据", 2, keyword_rank=1)
    vector_only = _search_result("仅向量证据", 1, vector_rank=1)

    fused = reciprocal_rank_fusion([vector_only, shared_vector], [shared_keyword])

    assert fused[0].source_document == "共同证据"
    assert fused[0].vector_rank == 2
    assert fused[0].keyword_rank == 1
    assert fused[0].rrf_score > fused[1].rrf_score


@pytest.mark.asyncio
async def test_hybrid_search_fuses_vector_and_keyword_results(monkeypatch):
    vector_rows = [
        _make_row("还款能力审查", "个人贷款管理办法", "第十二条", 1, row_id=1, similarity=0.8)
    ]
    keyword_rows = [
        _make_row(
            "月还款额不超过家庭月收入的50%",
            "成都商转公管理办法",
            "额度与还款能力",
            2,
            row_id=2,
            keyword_score=0.9,
        )
    ]
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_db_result(vector_rows), _db_result(keyword_rows)])

    import src.services.compliance.knowledge_base.search as mod

    monkeypatch.setattr(mod, "get_embeddings", AsyncMock(return_value=[[0.1] * 768]))
    results = await search_kb(session, "成都商转公月供收入比例")

    assert len(results) == 2
    assert {result.source_document for result in results} == {
        "个人贷款管理办法",
        "成都商转公管理办法",
    }
    assert any(result.keyword_rank == 1 for result in results)
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_keyword_search_survives_embedding_failure(monkeypatch):
    keyword_rows = [
        _make_row(
            "全国最低首付款比例不低于15%",
            "最低首付款政策",
            "全国最低首付款比例",
            1,
            row_id=3,
            keyword_score=1.0,
        )
    ]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_db_result(keyword_rows))

    import src.services.compliance.knowledge_base.search as mod

    monkeypatch.setattr(mod, "get_embeddings", AsyncMock(side_effect=RuntimeError("offline")))
    results = await search_kb(session, "最低首付15%")

    assert len(results) == 1
    assert results[0].source_document == "最低首付款政策"
    assert results[0].vector_rank is None
    assert results[0].keyword_rank == 1


@pytest.mark.asyncio
async def test_low_vector_similarity_without_keyword_match_returns_empty(monkeypatch):
    vector_rows = [_make_row("无关内容", "无关文件", None, 1, row_id=4, similarity=0.1)]
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_db_result(vector_rows), _db_result([])])

    import src.services.compliance.knowledge_base.search as mod

    monkeypatch.setattr(mod, "get_embeddings", AsyncMock(return_value=[[0.1] * 768]))
    assert await search_kb(session, "成都公积金") == []


@pytest.mark.asyncio
async def test_passes_date_and_provenance_filters_to_both_retrievers(monkeypatch):
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_db_result([]), _db_result([])])

    import src.services.compliance.knowledge_base.search as mod

    monkeypatch.setattr(mod, "get_embeddings", AsyncMock(return_value=[[0.1] * 768]))
    await search_kb(
        session,
        "成都公积金贷款",
        as_of=date(2026, 8, 25),
        jurisdiction="chengdu",
        source_type="official",
    )

    for call in session.execute.await_args_list:
        params = call.args[1]
        assert params["as_of"] == date(2026, 8, 25)
        assert params["jurisdiction"] == "chengdu"
        assert params["source_type"] == "official"
