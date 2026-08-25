# This project was developed with assistance from AI tools.
"""Tests for bounded Agentic RAG policy retrieval."""

from unittest.mock import AsyncMock

import pytest

from src.services.compliance.knowledge_base.controlled_retrieval import (
    _parse_rewrite,
    _rewrite_query_once,
    assess_evidence,
    retrieve_policy_evidence,
)
from src.services.compliance.knowledge_base.search import KBSearchResult


def _evidence(*, score=0.03, url="https://example.gov.cn/policy"):
    return KBSearchResult(
        chunk_text="全国最低首付款比例不低于15%",
        source_document="住房贷款首付款政策",
        section_ref="全国最低首付款比例",
        tier=1,
        tier_label="全国监管政策",
        similarity=0.8,
        boosted_similarity=0.9,
        effective_date="2024-09-24",
        issuer="监管机构",
        source_url=url,
        citation_id="POL-1-1",
        rrf_score=score,
    )


def test_assess_evidence_requires_official_url_and_relevance():
    assert assess_evidence([])[0] is False
    assert assess_evidence([_evidence(score=0.001)])[0] is False
    assert assess_evidence([_evidence(url=None)])[0] is False
    assert assess_evidence([_evidence()])[0] is True


def test_parse_rewrite_accepts_json_only_and_rejects_answer_text():
    assert _parse_rewrite('{"query":"成都住房公积金贷款首套认定"}', "成都公积金") == (
        "成都住房公积金贷款首套认定"
    )
    assert _parse_rewrite("成都首套执行什么政策", "成都公积金") is None


@pytest.mark.asyncio
async def test_qwen_rewrite_is_single_bounded_json_call(monkeypatch):
    completion = AsyncMock(return_value='{"query":"成都商转公月供收入比例"}')
    import src.services.compliance.knowledge_base.controlled_retrieval as mod

    monkeypatch.setattr(mod, "get_completion", completion)
    monkeypatch.setattr(mod, "get_model_config", lambda _tier: {"model_name": "qwen-test"})

    rewritten, model = await _rewrite_query_once("商转公月供最多多少")

    assert rewritten == "成都商转公月供收入比例"
    assert model == "qwen-test"
    completion.assert_awaited_once()
    kwargs = completion.await_args.kwargs
    assert kwargs["temperature"] == 0
    assert kwargs["max_tokens"] == 120
    assert kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_sufficient_first_search_does_not_call_qwen(monkeypatch):
    search = AsyncMock(return_value=[_evidence()])
    rewrite = AsyncMock()
    import src.services.compliance.knowledge_base.controlled_retrieval as mod

    monkeypatch.setattr(mod, "search_kb", search)
    monkeypatch.setattr(mod, "_rewrite_query_once", rewrite)

    outcome = await retrieve_policy_evidence(AsyncMock(), "全国首付比例")

    assert outcome.sufficient
    assert outcome.search_attempts == 1
    rewrite.assert_not_awaited()


@pytest.mark.asyncio
async def test_insufficient_search_rewrites_and_retries_exactly_once(monkeypatch):
    search = AsyncMock(side_effect=[[], [_evidence()]])
    rewrite = AsyncMock(return_value=("全国商业住房贷款最低首付款比例", "qwen-test"))
    import src.services.compliance.knowledge_base.controlled_retrieval as mod

    monkeypatch.setattr(mod, "search_kb", search)
    monkeypatch.setattr(mod, "_rewrite_query_once", rewrite)

    outcome = await retrieve_policy_evidence(AsyncMock(), "首付多少")

    assert outcome.sufficient
    assert outcome.rewrite_attempted
    assert outcome.search_attempts == 2
    assert outcome.rewrite_model == "qwen-test"
    assert search.await_count == 2
    rewrite.assert_awaited_once()


@pytest.mark.asyncio
async def test_second_insufficient_search_fails_closed(monkeypatch):
    search = AsyncMock(side_effect=[[], []])
    import src.services.compliance.knowledge_base.controlled_retrieval as mod

    monkeypatch.setattr(mod, "search_kb", search)
    monkeypatch.setattr(
        mod,
        "_rewrite_query_once",
        AsyncMock(return_value=("成都未知住房贷款政策", "qwen-test")),
    )

    outcome = await retrieve_policy_evidence(AsyncMock(), "未知问题")

    assert not outcome.sufficient
    assert outcome.search_attempts == 2
    assert search.await_count == 2


@pytest.mark.asyncio
async def test_invalid_rewrite_stops_without_unbounded_retry(monkeypatch):
    search = AsyncMock(return_value=[])
    import src.services.compliance.knowledge_base.controlled_retrieval as mod

    monkeypatch.setattr(mod, "search_kb", search)
    monkeypatch.setattr(mod, "_rewrite_query_once", AsyncMock(return_value=(None, "qwen-test")))

    outcome = await retrieve_policy_evidence(AsyncMock(), "未知问题")

    assert not outcome.sufficient
    assert outcome.rewrite_attempted
    assert outcome.search_attempts == 1
    assert search.await_count == 1
