# This project was developed with assistance from AI tools.
"""LangGraph tools for China-scenario underwriting decision management.

Wraps decision services, decision notifications and signing-element documents.

Design note -- session-per-tool-call:
    Each tool opens its own ``SessionLocal()`` context rather than sharing
    a single session across the agent turn.  See underwriter_tools.py
    for rationale.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Annotated

from db import Decision
from db.database import SessionLocal
from db.enums import DecisionType
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from sqlalchemy import select

from ..core.config import settings
from ..services.application import get_application
from ..services.audit import write_audit_event
from ..services.condition import get_outstanding_count
from ..services.decision import check_compliance_gate, propose_decision, render_decision
from ..services.rate_lock import get_rate_lock_status
from .disclosure_tools import generate_cd_text, generate_le_text, get_primary_borrower_name
from .shared import format_enum_label, user_context_from_state

logger = logging.getLogger(__name__)

_RECOMMENDATION_LABELS = {
    "approve": "可提交人工决策",
    "approve with conditions": "需重点人工复核",
    "deny": "需重点人工复核",
    "suspend": "需补充材料",
}


def _recommendation_label(value: str) -> str:
    """Localize legacy recommendation values stored by earlier demo versions."""
    text = str(value or "").strip()
    return _RECOMMENDATION_LABELS.get(text.lower(), text)


def _user_context_from_state(state: dict):
    return user_context_from_state(state, default_role="underwriter")


def _format_proposal(result: dict) -> str:
    """Format a proposal dict into a human-readable preview for the underwriter."""
    dt = format_enum_label(result["decision_type"])
    lines = [
        "待确认授信决定——等待审批人员确认",
        "================================",
        f"  申请：#{result['application_id']}",
        f"  拟作决定：{dt}",
        f"  决策依据：{result['rationale']}",
    ]

    if result.get("new_stage"):
        stage_label = format_enum_label(result["new_stage"])
        lines.append(
            f"  阶段变化：{format_enum_label(result['current_stage'])} → {stage_label}"
        )

    if result.get("outstanding_conditions", 0) > 0:
        lines.append(f"  待处理审批条件：{result['outstanding_conditions']} 项")

    if result.get("ai_recommendation"):
        lines.append(f"  系统辅助建议：{_recommendation_label(result['ai_recommendation'])}")
        if result.get("ai_agreement") is True:
            lines.append("  与系统辅助建议一致：是")
        elif result.get("ai_agreement") is False:
            lines.append("  与系统辅助建议一致：否（须填写人工调整理由）")
            if result.get("override_rationale"):
                lines.append(f"  人工调整理由：{result['override_rationale']}")

    if result.get("denial_reasons"):
        lines.append("  未通过原因：")
        for i, reason in enumerate(result["denial_reasons"], 1):
            lines.append(f"    {i}. {reason}")

    # Add proposal_id if present
    if result.get("proposal_id"):
        lines.extend(
            [
                "",
                f"提案标识：{result['proposal_id']}",
                "",
                "该决定尚未写入业务记录。",
                "请向审批人员展示以上内容并取得明确确认。",
                f"确认后须携带提案标识“{result['proposal_id']}”执行确认操作。",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "该决定尚未写入业务记录。",
                "请先向审批人员展示以上内容并取得明确确认。",
            ]
        )

    return "\n".join(lines)


def _format_confirmed(result: dict, rationale: str) -> str:
    """Format a confirmed decision dict into output text."""
    dt = format_enum_label(result["decision_type"])
    lines = [
        f"申请 #{result['application_id']} 的授信决定已记录：",
        f"  决策编号：{result.get('id', '暂无')}",
        f"  类型：{dt}",
        f"  决策依据：{rationale}",
    ]

    if result.get("new_stage"):
        stage_label = format_enum_label(result["new_stage"])
        lines.append(f"  新阶段：{stage_label}")

    if result.get("ai_recommendation"):
        lines.append(f"  系统辅助建议：{_recommendation_label(result['ai_recommendation'])}")
        if result.get("ai_agreement") is True:
            lines.append("  与系统辅助建议一致：是")
        elif result.get("ai_agreement") is False:
            lines.append("  与系统辅助建议一致：否")
            if result.get("override_rationale"):
                lines.append(f"  人工调整理由：{result['override_rationale']}")

    if result.get("denial_reasons"):
        lines.append("  未通过原因：")
        for i, reason in enumerate(result["denial_reasons"], 1):
            lines.append(f"    {i}. {reason}")

    return "\n".join(lines)


@tool
async def uw_render_decision(
    application_id: int,
    decision: str,
    rationale: str,
    confirmed: bool = False,
    proposal_id: str | None = None,
    denial_reasons: list[str] | None = None,
    credit_score_used: int | None = None,
    credit_score_source: str | None = None,
    contributing_factors: str | None = None,
    override_rationale: str | None = None,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Render an underwriting decision on a loan application.

    This tool uses a two-phase flow to ensure human confirmation:

    Phase 1 (confirmed=false, the default): Returns a PROPOSAL showing
    what the decision would do (decision type, stage transition, AI
    agreement). The proposal is stored in agent state with a unique
    proposal_id. No database records are created. You MUST present
    this proposal to the underwriter and wait for their explicit
    confirmation.

    Phase 2 (confirmed=true): After the underwriter confirms, call
    again with confirmed=true and the proposal_id from Phase 1 to
    execute the decision. This validates the proposal_id, creates
    the decision record, transitions the application stage, and
    writes audit events.

    IMPORTANT: Never set confirmed=true without first showing the
    proposal to the underwriter and receiving their explicit approval.
    The proposal_id parameter is required when confirmed=true.

    Args:
        application_id: The loan application ID.
        decision: One of "approve", "deny", or "suspend".
        rationale: Explanation for the decision.
        confirmed: Set to true only after the underwriter confirms the proposal.
        proposal_id: Required when confirmed=true. The ID from Phase 1 proposal.
        denial_reasons: Required for denials. List of specific reasons.
        credit_score_used: Credit score at time of decision (for denials).
        credit_score_source: Credit bureau source (for denials).
        contributing_factors: Factors that contributed to the decision.
        override_rationale: Explanation when overriding AI recommendation.
    """
    import uuid

    user = _user_context_from_state(state)
    decision_lower = decision.strip().lower()

    async with SessionLocal() as session:
        # Compliance gate for approvals (both phases)
        if decision_lower == "approve":
            gate_error = await check_compliance_gate(session, application_id)
            if gate_error:
                return gate_error

        if not confirmed:
            # Phase 1: propose only
            result = await propose_decision(
                session,
                user,
                application_id,
                decision_lower,
                rationale,
                denial_reasons=denial_reasons,
                override_rationale=override_rationale,
            )

            if result is None:
                return f"未找到申请 #{application_id}，或您没有查看权限。"
            if "error" in result:
                return result["error"]

            # Generate proposal_id and store in state
            proposal_id_generated = str(uuid.uuid4())

            # Store proposal in state
            if state is not None:
                if "decision_proposals" not in state:
                    state["decision_proposals"] = {}
                state["decision_proposals"][proposal_id_generated] = {
                    "application_id": application_id,
                    "decision": decision_lower,
                    "rationale": rationale,
                    "denial_reasons": denial_reasons,
                    "override_rationale": override_rationale,
                }

            # Add proposal_id to result for output
            result["proposal_id"] = proposal_id_generated

            return _format_proposal(result)

        # Phase 2: confirmed -- validate proposal_id and persist
        if proposal_id is None:
            return (
                "确认失败：确认授信决定时必须提供提案标识。请先生成待确认提案，"
                "取得审批人员明确确认后再执行。"
            )

        # Validate proposal_id exists in state
        if state is None or "decision_proposals" not in state:
            return (
                f"确认失败：未找到提案标识“{proposal_id}”，该提案可能无效或已过期。"
                "请重新生成待确认提案。"
            )

        proposal = state["decision_proposals"].get(proposal_id)
        if proposal is None:
            return (
                f"确认失败：未找到提案标识“{proposal_id}”。请核对标识或重新生成提案。"
            )

        # Validate proposal matches current parameters
        if proposal["application_id"] != application_id:
            return (
                f"确认失败：提案标识“{proposal_id}”属于申请 #{proposal['application_id']}，"
                f"与当前申请 #{application_id} 不一致。"
            )

        if proposal["decision"] != decision_lower:
            return (
                f"确认失败：提案中的决定类型为“{proposal['decision']}”，"
                f"与当前提交的“{decision_lower}”不一致。"
            )

        # Proceed with rendering the decision
        result = await render_decision(
            session,
            user,
            application_id,
            decision_lower,
            rationale,
            denial_reasons=denial_reasons,
            credit_score_used=credit_score_used,
            credit_score_source=credit_score_source,
            contributing_factors=contributing_factors,
            override_rationale=override_rationale,
        )

        # Clear the proposal from state after successful confirmation
        if state is not None and "decision_proposals" in state:
            state["decision_proposals"].pop(proposal_id, None)

    if result is None:
        return f"未找到申请 #{application_id}，或您没有查看权限。"
    if "error" in result:
        return result["error"]

    return _format_confirmed(result, rationale)


@tool
async def uw_draft_adverse_action(
    application_id: int,
    decision_id: int | None = None,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Draft a Chinese demo credit-decision notice for a denied application.

    Args:
        application_id: The loan application ID.
        decision_id: Optional decision ID. If omitted, uses the most recent
            DENIED decision for the application.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return f"未找到申请 #{application_id}，或您没有查看权限。"

        if decision_id is not None:
            # Fetch specific decision
            dec_stmt = select(Decision).where(
                Decision.id == decision_id,
                Decision.application_id == application_id,
            )
        else:
            # Auto-find latest DENIED decision
            dec_stmt = (
                select(Decision)
                .where(
                    Decision.application_id == application_id,
                    Decision.decision_type == DecisionType.DENIED,
                )
                .order_by(Decision.created_at.desc())
                .limit(1)
            )

        dec_result = await session.execute(dec_stmt)
        dec = dec_result.scalar_one_or_none()

        if dec is None:
            if decision_id is not None:
                return f"申请 #{application_id} 中未找到决策 #{decision_id}。"
            return f"申请 #{application_id} 中未找到“未通过”决策。"

        if dec.decision_type != DecisionType.DENIED:
            return (
                f"决策 #{dec.id} 的类型为“{format_enum_label(dec.decision_type.value)}”；"
                "只有未通过的申请才能生成授信决定告知书。"
            )

        # Get borrower info
        borrower_name = await get_primary_borrower_name(session, application_id)

        # Parse denial reasons
        denial_reasons = []
        if dec.denial_reasons:
            try:
                denial_reasons = json.loads(dec.denial_reasons)
            except (json.JSONDecodeError, TypeError):
                denial_reasons = [dec.denial_reasons]

        # Build notice
        today = datetime.now(UTC).astimezone().strftime("%Y年%m月%d日")
        lines = [
            "授信决定告知书（演示）",
            "======================",
            f"日期：{today}",
            f"借款人：{borrower_name}",
            f"申请编号：#{application_id}",
            "",
            "经有权审批人员审核，本次住房贷款申请未通过。主要原因为：",
        ]

        if denial_reasons:
            for i, reason in enumerate(denial_reasons, 1):
                lines.append(f"  {i}. {reason}")
        else:
            lines.append("  暂未记录具体原因，请补充后再向申请人送达。")

        # Credit score disclosure
        if dec.credit_score_used is not None:
            lines.extend(
                [
                    "",
                    "征信评分说明（演示字段）：",
                    f"  决策时使用的评分：{dec.credit_score_used}",
                    f"  数据来源：{dec.credit_score_source or '未记录'}",
                    "  本项目不连接真实征信机构；正式业务须基于合法授权取得的征信信息。",
                ]
            )

        if dec.contributing_factors:
            lines.extend(
                [
                    "",
                    "其他影响因素：",
                    f"  {dec.contributing_factors}",
                ]
            )

        lines.extend(
            [
                "",
                "申请人权益提示：",
                "- 有权了解与本次授信决定直接相关的主要原因；",
                "- 对征信信息存在错误、遗漏的，可依法向征信机构或信息提供者提出异议；",
                "- 对服务或处理结果有异议的，可通过金融机构公布的客服、投诉及争议解决渠道反映；",
                "",
                settings.COMPANY_NAME,
                "",
                "参考依据：《征信业管理条例》及金融消费者权益保护相关规定。",
                "提示：本文件仅用于虚构项目演示，不替代金融机构正式授信决定告知书或法律意见。",
            ]
        )

        notice_text = "\n".join(lines)

        # Store as audit event
        await write_audit_event(
            session,
            event_type="adverse_action_notice",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "decision_id": dec.id,
                "borrower_name": borrower_name,
                "denial_reasons": denial_reasons,
                "credit_score_used": dec.credit_score_used,
            },
        )
        await session.commit()

    return notice_text


@tool
async def uw_generate_le(
    application_id: int,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Generate a simulated Chinese housing-loan terms confirmation.

    Args:
        application_id: The loan application ID.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return f"未找到申请 #{application_id}，或您没有查看权限。"

        le_text = await generate_le_text(session, user, app, application_id)

        # Update LE delivery date
        app.le_delivery_date = datetime.now(UTC)

        # Extract values for audit (redundant calc but simpler than returning from helper)
        loan_amount = float(app.loan_amount) if app.loan_amount else 0
        rate_lock = await get_rate_lock_status(session, user, application_id)
        rate = 3.5
        if rate_lock and rate_lock.get("locked_rate"):
            rate = float(rate_lock["locked_rate"])
        loan_type = app.loan_type.value if app.loan_type else "conventional_30"
        term_years = 15 if loan_type == "conventional_15" else 30

        await write_audit_event(
            session,
            event_type="le_generated",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "loan_amount": loan_amount,
                "rate": rate,
                "term_years": term_years,
            },
        )
        await session.commit()

    return le_text


@tool
async def uw_generate_cd(
    application_id: int,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Generate a simulated Chinese signing-elements confirmation.

    Args:
        application_id: The loan application ID.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return f"未找到申请 #{application_id}，或您没有查看权限。"

        # Condition gate: all conditions must be cleared/waived
        outstanding = await get_outstanding_count(session, application_id)
        if outstanding > 0:
            return (
                f"申请 #{application_id} 仍有 {outstanding} 项审批条件未完成，暂不能生成"
                "签约要素确认书。请先完成或由有权人员豁免全部条件。"
            )

        cd_text = await generate_cd_text(session, user, app, application_id)

        # Update CD delivery date
        app.cd_delivery_date = datetime.now(UTC)

        # Extract values for audit
        loan_amount = float(app.loan_amount) if app.loan_amount else 0
        rate_lock = await get_rate_lock_status(session, user, application_id)
        rate = 3.5
        if rate_lock and rate_lock.get("locked_rate"):
            rate = float(rate_lock["locked_rate"])
        loan_type = app.loan_type.value if app.loan_type else "conventional_30"
        term_years = 15 if loan_type == "conventional_15" else 30

        await write_audit_event(
            session,
            event_type="cd_generated",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "loan_amount": loan_amount,
                "rate": rate,
                "term_years": term_years,
            },
        )
        await session.commit()

    return cd_text
