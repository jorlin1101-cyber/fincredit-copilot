# This project was developed with assistance from AI tools.
"""LangGraph tools for compliance knowledge base search.

Provides the kb_search tool that agents can use to query the three-tier
compliance knowledge base (federal regulations, agency guidelines,
internal policies) with conflict detection and audit logging.

Design note -- session-per-tool-call:
    Each tool opens its own ``SessionLocal()`` context rather than sharing
    a single session across the agent turn.  See loan_officer_tools.py
    for rationale.
"""

import logging
from datetime import date
from typing import Annotated

from db.database import SessionLocal
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from ..services.audit import write_audit_event
from ..services.compliance.knowledge_base.conflict import detect_conflicts
from ..services.compliance.knowledge_base.controlled_retrieval import retrieve_policy_evidence

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "\n提示：本结果仅供项目演示和授信辅助，不构成法律、监管或授信意见；"
    "实际业务须由有权人员核验官方原文并完成审批。"
)


@tool
async def kb_search(
    query: str,
    state: Annotated[dict, InjectedState],
    as_of: str | None = None,
) -> str:
    """检索全国及成都住房贷款政策证据，证据不足时停止生成结论。

    Args:
        query: 监管或机构规则问题。
        state: Agent 上下文。
        as_of: 政策适用日期（YYYY-MM-DD）；不填则使用申请日期或当天。
    """
    user_id = state.get("user_id", "anonymous")
    user_role = state.get("user_role", "")
    session_id = state.get("session_id")
    trace_id = state.get("trace_id") or session_id
    application_id = state.get("application_id")

    raw_as_of = as_of or state.get("application_date")
    try:
        policy_date = date.fromisoformat(raw_as_of) if raw_as_of else date.today()
    except (TypeError, ValueError):
        return "政策适用日期格式无效，请使用 YYYY-MM-DD。" + _DISCLAIMER

    async with SessionLocal() as session:
        outcome = await retrieve_policy_evidence(session, query, as_of=policy_date)
        results = outcome.results

        await write_audit_event(
            session,
            event_type="agent_tool_called",
            session_id=session_id,
            user_id=user_id,
            user_role=user_role,
            application_id=application_id,
            event_data={
                "tool": "kb_search",
                "query": query,
                "effective_query": outcome.effective_query,
                "as_of": policy_date.isoformat(),
                "trace_id": trace_id,
                "result_count": len(results),
                "citation_ids": [result.citation_id for result in results],
                "retrieval_status": outcome.status,
                "retrieval_reason": outcome.reason,
                "search_attempts": outcome.search_attempts,
                "rewrite_attempted": outcome.rewrite_attempted,
                "rewritten_query": outcome.rewritten_query,
                "rewrite_model": outcome.rewrite_model,
                "rewrite_input_tokens": outcome.rewrite_input_tokens,
                "rewrite_output_tokens": outcome.rewrite_output_tokens,
                "prompt_version": outcome.prompt_version,
            },
        )

        if not outcome.sufficient:
            await session.commit()
            return (
                "受控 Agentic RAG：政策证据不足，系统已停止生成政策结论并转人工复核。\n"
                f"原因：{outcome.reason}\n"
                f"检索次数：{outcome.search_attempts}（最多一次查询改写与一次重试）。" + _DISCLAIMER
            )

        conflicts = detect_conflicts(results)

        if conflicts:
            await write_audit_event(
                session,
                event_type="system",
                session_id=session_id,
                user_id=user_id,
                user_role=user_role,
                event_data={
                    "action": "kb_conflict_detected",
                    "query": query,
                    "trace_id": trace_id,
                    "conflict_count": len(conflicts),
                    "conflict_types": [c.conflict_type for c in conflicts],
                },
            )

        await session.commit()

    lines = [
        f"受控 Agentic RAG 政策证据（{len(results)}条，适用日期：{policy_date.isoformat()}）：\n"
    ]

    for i, r in enumerate(results, 1):
        citation = r.citation_id or f"POL-{i}"
        lines.append(f"{i}. [{citation}] [{r.tier_label}] {r.source_document}")
        if r.issuer:
            lines.append(f"   发布机构：{r.issuer}")
        if r.version:
            lines.append(f"   版本：{r.version}")
        if r.section_ref:
            lines.append(f"   条款定位：{r.section_ref}")
        if r.effective_date:
            validity = f"{r.effective_date} 起"
            if r.expires_at:
                validity += f"，至 {r.expires_at}"
            lines.append(f"   有效期：{validity}")
        if r.source_url:
            lines.append(f"   官方来源：{r.source_url}")
        elif r.source_type == "internal_demo":
            lines.append("   来源标识：虚构内部演示规则（非监管政策）")
        lines.append(f"   证据摘要：{r.chunk_text[:500]}")
        lines.append("")

    if conflicts:
        lines.append("检测到规则差异，须人工判断适用关系：")
        for c in conflicts:
            lines.append(f"  - {c.conflict_type}: {c.description}")
        lines.append("")

    lines.append(_DISCLAIMER)

    return "\n".join(lines)
