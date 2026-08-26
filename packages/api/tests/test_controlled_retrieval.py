# This project was developed with assistance from AI tools.
"""Tests for bounded Agentic RAG policy retrieval."""

from unittest.mock import AsyncMock

import pytest

from src.inference.client import CompletionResult
from src.services.compliance.knowledge_base.controlled_retrieval import (
    _expand_query,
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
        version="2024-v1",
        citation_id="POL-1-1",
        rrf_score=score,
    )


def test_assess_evidence_requires_official_url_and_relevance():
    assert assess_evidence([])[0] is False
    assert assess_evidence([_evidence(score=0.001)])[0] is False
    assert assess_evidence([_evidence(url=None)])[0] is False
    missing_version = _evidence()
    missing_version.version = None
    assert assess_evidence([missing_version])[0] is False
    missing_citation = _evidence()
    missing_citation.citation_id = None
    assert assess_evidence([missing_citation])[0] is False
    assert assess_evidence([_evidence()])[0] is True


def test_assess_evidence_ignores_incomplete_lower_ranked_candidate():
    incomplete = _evidence()
    incomplete.section_ref = None

    assert assess_evidence([_evidence(), incomplete])[0] is True


def test_assess_evidence_requires_named_policy_version_to_match():
    evidence = _evidence()
    evidence.version = "成公积金〔2025〕8号"

    assert assess_evidence([evidence], query="成公积金〔2026〕12号是否有效")[0] is False
    evidence.version = "成公积金〔2026〕12号"
    assert assess_evidence([evidence], query="成公积金〔2026〕12号是否有效")[0] is True


def test_domain_synonyms_are_added_without_removing_constraints():
    expanded = _expand_query("2026年3月25日成都新房公积金政策")

    assert "2026年3月25日" in expanded
    assert "成都" in expanded
    assert "新建住房阶段性安排" in expanded
    assert expanded.startswith("新建住房阶段性安排")


def test_parse_rewrite_accepts_json_only_and_rejects_answer_text():
    assert _parse_rewrite('{"query":"成都住房公积金贷款首套认定"}', "成都公积金") == (
        "成都住房公积金贷款首套认定"
    )
    assert _parse_rewrite("成都首套执行什么政策", "成都公积金") is None


@pytest.mark.asyncio
async def test_qwen_rewrite_is_single_bounded_json_call(monkeypatch):
    completion = AsyncMock(
        return_value=CompletionResult(
            content='{"query":"成都商转公月供收入比例"}',
            model="qwen-test",
            input_tokens=35,
            output_tokens=12,
        )
    )
    import src.services.compliance.knowledge_base.controlled_retrieval as mod

    monkeypatch.setattr(mod, "get_completion_result", completion)
    monkeypatch.setattr(mod, "get_model_config", lambda _tier: {"model_name": "qwen-test"})

    rewritten, model, input_tokens, output_tokens = await _rewrite_query_once("商转公月供最多多少")

    assert rewritten == "成都商转公月供收入比例"
    assert model == "qwen-test"
    assert input_tokens == 35
    assert output_tokens == 12
    completion.assert_awaited_once()
    kwargs = completion.await_args.kwargs
    assert kwargs["temperature"] == 0
    assert kwargs["max_tokens"] == 120
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["extra_body"] == {"enable_thinking": False}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "北京住房公积金贷款最高额度是多少？",
        "成都今天各家银行实时房贷利率分别是多少？",
        "企业经营贷款担保费率是多少？",
        "请查询某位真实客户的个人征信逾期记录。",
        "汽车消费贷款最低首付比例是多少？",
    ],
)
async def test_out_of_scope_query_fails_before_search_or_model(monkeypatch, query):
    search = AsyncMock()
    rewrite = AsyncMock()
    import src.services.compliance.knowledge_base.controlled_retrieval as mod

    monkeypatch.setattr(mod, "search_kb", search)
    monkeypatch.setattr(mod, "_rewrite_query_once", rewrite)

    outcome = await retrieve_policy_evidence(AsyncMock(), query)

    assert not outcome.sufficient
    assert outcome.search_attempts == 1
    search.assert_not_awaited()
    rewrite.assert_not_awaited()


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
    rewrite = AsyncMock(return_value=("全国商业住房贷款最低首付款比例", "qwen-test", 30, 10))
    import src.services.compliance.knowledge_base.controlled_retrieval as mod

    monkeypatch.setattr(mod, "search_kb", search)
    monkeypatch.setattr(mod, "_rewrite_query_once", rewrite)

    outcome = await retrieve_policy_evidence(AsyncMock(), "首付多少")

    assert outcome.sufficient
    assert outcome.rewrite_attempted
    assert outcome.search_attempts == 2
    assert outcome.rewrite_model == "qwen-test"
    assert outcome.rewrite_input_tokens == 30
    assert outcome.rewrite_output_tokens == 10
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
        AsyncMock(return_value=("成都未知住房贷款政策", "qwen-test", 30, 10)),
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
    monkeypatch.setattr(
        mod,
        "_rewrite_query_once",
        AsyncMock(return_value=(None, "qwen-test", None, None)),
    )

    outcome = await retrieve_policy_evidence(AsyncMock(), "未知问题")

    assert not outcome.sufficient
    assert outcome.rewrite_attempted
    assert outcome.search_attempts == 1
    assert search.await_count == 1
