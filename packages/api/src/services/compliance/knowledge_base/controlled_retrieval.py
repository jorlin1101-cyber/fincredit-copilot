# This project was developed with assistance from AI tools.
"""Controlled Agentic RAG with one bounded query rewrite and fail-closed fallback."""

import json
import logging
import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from src.inference.client import get_completion_result
from src.inference.config import get_model_config

from .search import KBSearchResult, search_kb

logger = logging.getLogger(__name__)

REWRITE_PROMPT_VERSION = "policy-query-rewrite-v1"
_MIN_RRF_SCORE = 0.015
_POLICY_REFERENCE_PATTERN = re.compile(r"[\u4e00-\u9fff]{1,12}〔\d{4}〕\d+号")
_UNSUPPORTED_LOCALITIES = (
    "北京",
    "上海",
    "天津",
    "重庆",
    "广州",
    "深圳",
    "杭州",
    "南京",
    "武汉",
    "西安",
)
_UNSUPPORTED_PRODUCTS = ("汽车消费贷款", "车贷", "企业经营贷款", "经营贷")
_QUERY_EXPANSIONS = {
    "新房": "新建住房阶段性安排",
    "首付": "最低首付款比例",
    "首套": "首套政策认定",
    "商转公": "商业性个人住房贷款转住房公积金个人住房贷款",
}


@dataclass
class RetrievalOutcome:
    """Inspectable result of the bounded policy evidence retrieval process."""

    original_query: str
    effective_query: str
    results: list[KBSearchResult]
    status: str
    reason: str
    rewrite_attempted: bool = False
    rewritten_query: str | None = None
    rewrite_model: str | None = None
    rewrite_input_tokens: int | None = None
    rewrite_output_tokens: int | None = None
    prompt_version: str = REWRITE_PROMPT_VERSION
    search_attempts: int = 1

    @property
    def sufficient(self) -> bool:
        return self.status == "sufficient"


def _scope_guard(query: str) -> str | None:
    """Reject requests outside the declared nationwide + Chengdu housing scope."""
    if any(locality in query for locality in _UNSUPPORTED_LOCALITIES):
        return "地方知识库仅覆盖成都市，无法回答其他城市的地方政策"
    if any(product in query for product in _UNSUPPORTED_PRODUCTS):
        return "知识库仅覆盖住房贷款，不覆盖经营贷或汽车消费贷款"
    if ("实时" in query or "今天" in query) and ("利率" in query or "各家银行" in query):
        return "政策知识库不提供各银行实时利率"
    if "真实客户" in query or ("个人征信" in query and "记录" in query):
        return "政策检索不能查询真实客户的个人征信记录"
    return None


def _expand_query(query: str) -> str:
    """Add deterministic domain synonyms without removing user constraints."""
    expansions = [term for marker, term in _QUERY_EXPANSIONS.items() if marker in query]
    return f"{' '.join(expansions)} {query}".strip()


def _verified_evidence(results: list[KBSearchResult]) -> list[KBSearchResult]:
    """Keep only chunks whose provenance can be independently verified."""
    return [
        result
        for result in results
        if result.source_document
        and result.section_ref
        and result.effective_date
        and result.version
        and result.citation_id
        and (result.source_type != "official" or result.source_url)
    ]


def assess_evidence(results: list[KBSearchResult], *, query: str | None = None) -> tuple[bool, str]:
    """Require relevance plus citation provenance before evidence may reach an Agent."""
    verified = _verified_evidence(results)
    if not verified:
        return False, "未检索到与问题相关且在有效期内的政策证据"
    top = verified[0]
    if top.rrf_score < _MIN_RRF_SCORE:
        return False, "检索相关性低于受控阈值"
    references = _POLICY_REFERENCE_PATTERN.findall(query or "")
    if references:
        evidence_text = " ".join(
            " ".join(
                filter(
                    None,
                    [result.version, result.source_document, result.section_ref, result.chunk_text],
                )
            )
            for result in verified
        )
        if not all(reference in evidence_text for reference in references):
            return False, "用户点名的政策版本在指定日期内无有效证据"
    return True, "已获得带版本、有效期和条款定位的可核验政策证据"


def _parse_rewrite(content: str, original_query: str) -> str | None:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        cleaned = cleaned.removesuffix("```").strip()
    try:
        payload = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return None
    rewritten = str(payload.get("query", "")).strip()
    if not rewritten or rewritten == original_query or len(rewritten) > 200:
        return None
    return rewritten


async def _rewrite_query_once(
    query: str,
) -> tuple[str | None, str | None, int | None, int | None]:
    """Use the configured Qwen text model once; never generate a policy answer here."""
    model_name = str(get_model_config("llm")["model_name"])
    messages = [
        {
            "role": "system",
            "content": (
                "你是住房贷款政策检索查询改写器，只能改写检索词，不能回答政策问题。"
                "保留地点、日期、贷款类型、比例、文件号等约束。"
                '只输出JSON对象：{"query":"改写后的中文检索词"}。'
            ),
        },
        {"role": "user", "content": query},
    ]
    try:
        result = await get_completion_result(
            messages,
            tier="llm",
            temperature=0,
            max_tokens=120,
            response_format={"type": "json_object"},
            extra_body={"enable_thinking": False},
        )
    except Exception:
        logger.warning("Policy query rewrite failed", exc_info=True)
        return None, model_name, None, None
    return (
        _parse_rewrite(result.content, query),
        model_name,
        result.input_tokens,
        result.output_tokens,
    )


async def retrieve_policy_evidence(
    session: AsyncSession,
    query: str,
    *,
    as_of: date | None = None,
    jurisdiction: str | None = None,
) -> RetrievalOutcome:
    """Retrieve evidence, optionally rewrite once, then stop rather than hallucinate."""
    scope_reason = _scope_guard(query)
    if scope_reason:
        return RetrievalOutcome(
            original_query=query,
            effective_query=query,
            results=[],
            status="insufficient",
            reason=scope_reason,
        )

    expanded_query = _expand_query(query)
    first_results = await search_kb(
        session,
        expanded_query,
        as_of=as_of,
        jurisdiction=jurisdiction,
    )
    first_results = _verified_evidence(first_results)
    sufficient, reason = assess_evidence(first_results, query=query)
    if sufficient:
        return RetrievalOutcome(
            original_query=query,
            effective_query=expanded_query,
            results=first_results,
            status="sufficient",
            reason=reason,
        )

    rewritten_query, model_name, input_tokens, output_tokens = await _rewrite_query_once(query)
    if not rewritten_query:
        return RetrievalOutcome(
            original_query=query,
            effective_query=query,
            results=first_results,
            status="insufficient",
            reason=f"{reason}；一次查询改写未产生有效检索词",
            rewrite_attempted=True,
            rewrite_model=model_name,
            rewrite_input_tokens=input_tokens,
            rewrite_output_tokens=output_tokens,
        )

    expanded_rewrite = _expand_query(rewritten_query)
    retry_results = await search_kb(
        session,
        expanded_rewrite,
        as_of=as_of,
        jurisdiction=jurisdiction,
    )
    retry_results = _verified_evidence(retry_results)
    sufficient, retry_reason = assess_evidence(retry_results, query=query)
    return RetrievalOutcome(
        original_query=query,
        effective_query=expanded_rewrite,
        results=retry_results,
        status="sufficient" if sufficient else "insufficient",
        reason=retry_reason,
        rewrite_attempted=True,
        rewritten_query=rewritten_query,
        rewrite_model=model_name,
        rewrite_input_tokens=input_tokens,
        rewrite_output_tokens=output_tokens,
        search_attempts=2,
    )
