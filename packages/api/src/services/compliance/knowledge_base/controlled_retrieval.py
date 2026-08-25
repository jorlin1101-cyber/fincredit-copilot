# This project was developed with assistance from AI tools.
"""Controlled Agentic RAG with one bounded query rewrite and fail-closed fallback."""

import json
import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from src.inference.client import get_completion
from src.inference.config import get_model_config

from .search import KBSearchResult, search_kb

logger = logging.getLogger(__name__)

REWRITE_PROMPT_VERSION = "policy-query-rewrite-v1"
_MIN_RRF_SCORE = 0.015


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
    prompt_version: str = REWRITE_PROMPT_VERSION
    search_attempts: int = 1

    @property
    def sufficient(self) -> bool:
        return self.status == "sufficient"


def assess_evidence(results: list[KBSearchResult]) -> tuple[bool, str]:
    """Require relevance plus citation provenance before evidence may reach an Agent."""
    if not results:
        return False, "未检索到与问题相关且在有效期内的政策证据"
    top = results[0]
    if top.rrf_score < _MIN_RRF_SCORE:
        return False, "检索相关性低于受控阈值"
    for result in results:
        if result.source_type == "official" and not result.source_url:
            return False, "官方政策证据缺少可核验来源网址"
        if not result.source_document or not result.section_ref:
            return False, "政策证据缺少文件名或条款定位"
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


async def _rewrite_query_once(query: str) -> tuple[str | None, str | None]:
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
        content = await get_completion(
            messages,
            tier="llm",
            temperature=0,
            max_tokens=120,
            response_format={"type": "json_object"},
        )
    except Exception:
        logger.warning("Policy query rewrite failed", exc_info=True)
        return None, model_name
    return _parse_rewrite(content, query), model_name


async def retrieve_policy_evidence(
    session: AsyncSession,
    query: str,
    *,
    as_of: date | None = None,
    jurisdiction: str | None = None,
) -> RetrievalOutcome:
    """Retrieve evidence, optionally rewrite once, then stop rather than hallucinate."""
    first_results = await search_kb(
        session,
        query,
        as_of=as_of,
        jurisdiction=jurisdiction,
    )
    sufficient, reason = assess_evidence(first_results)
    if sufficient:
        return RetrievalOutcome(
            original_query=query,
            effective_query=query,
            results=first_results,
            status="sufficient",
            reason=reason,
        )

    rewritten_query, model_name = await _rewrite_query_once(query)
    if not rewritten_query:
        return RetrievalOutcome(
            original_query=query,
            effective_query=query,
            results=first_results,
            status="insufficient",
            reason=f"{reason}；一次查询改写未产生有效检索词",
            rewrite_attempted=True,
            rewrite_model=model_name,
        )

    retry_results = await search_kb(
        session,
        rewritten_query,
        as_of=as_of,
        jurisdiction=jurisdiction,
    )
    sufficient, retry_reason = assess_evidence(retry_results)
    return RetrievalOutcome(
        original_query=query,
        effective_query=rewritten_query,
        results=retry_results,
        status="sufficient" if sufficient else "insufficient",
        reason=retry_reason,
        rewrite_attempted=True,
        rewritten_query=rewritten_query,
        rewrite_model=model_name,
        search_attempts=2,
    )
