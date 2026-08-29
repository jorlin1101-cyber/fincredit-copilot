# This project was developed with assistance from AI tools.
"""LangGraph tools for the underwriter assistant agent.

These wrap existing services so the underwriter agent can review the
underwriting queue, inspect application details, save risk assessments,
and generate preliminary recommendations.

Risk assessment *computation* is handled by MCP tools (see mcp_server.py).
The uw_save_risk_assessment tool here handles DB persistence and audit only.

Design note -- session-per-tool-call:
    Each tool opens its own ``SessionLocal()`` context rather than sharing
    a single session across the agent turn.  This is intentional: LangGraph
    tool nodes run as independent async tasks and may execute in any order,
    so sharing a session would risk interleaved flushes, stale reads, and
    MissingGreenlet errors.  The per-tool pattern keeps each DB interaction
    self-contained and avoids cross-tool state leakage.
"""

import logging
from typing import Annotated

from db import CreditReport
from db.database import SessionLocal
from db.enums import ApplicationStage
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from sqlalchemy import select

from ..schemas.urgency import UrgencyLevel
from ..services.application import get_application, get_financials, list_applications
from ..services.audit import write_audit_event
from ..services.condition import get_conditions
from ..services.deterministic_assessment import run_deterministic_assessment
from ..services.document import list_documents
from ..services.rate_lock import get_rate_lock_status
from ..services.risk_assessment import (
    create_risk_assessment,
    get_latest_risk_assessment,
    update_recommendation,
)
from ..services.urgency import compute_urgency
from .mcp_integration import get_predictive_tool, is_predictive_model_available
from .risk_tools import (
    compute_recommendation,
    compute_risk_factors,
    extract_borrower_info,
)
from .shared import format_enum_label, user_context_from_state

logger = logging.getLogger(__name__)

_URGENCY_ORDER = {
    UrgencyLevel.CRITICAL: 0,
    UrgencyLevel.HIGH: 1,
    UrgencyLevel.MEDIUM: 2,
    UrgencyLevel.NORMAL: 3,
}

_URGENCY_LABELS = {
    UrgencyLevel.CRITICAL: "紧急",
    UrgencyLevel.HIGH: "高",
    UrgencyLevel.MEDIUM: "中",
    UrgencyLevel.NORMAL: "常规",
}

_LOAN_TYPE_LABELS = {
    "conventional_30": "30年期商业性个人住房贷款",
    "conventional_15": "15年期商业性个人住房贷款",
    "fha": "住房公积金个人住房贷款",
    "va": "商业贷款与公积金组合贷款",
    "jumbo": "大额商业性个人住房贷款",
    "usda": "县域住房贷款（演示产品）",
    "arm": "LPR浮动利率个人住房贷款",
}

_DOC_TYPE_LABELS = {
    "id_card": "居民身份证",
    "income_certificate": "收入证明",
    "w2": "工资与税务证明（兼容材料）",
    "pay_stub": "近期工资单",
    "tax_return": "个人所得税纳税记录",
    "bank_statement": "银行流水",
    "drivers_license": "身份证明（兼容材料）",
    "property_appraisal": "房产评估报告",
    "homeowners_insurance": "房屋保险凭证",
    "purchase_agreement": "购房合同",
    "other": "其他材料",
}

_RATE_STATUS_LABELS = {"active": "有效", "expired": "已到期", "none": "未锁定"}


def _person_name(first_name: str, last_name: str) -> str:
    if any("\u4e00" <= char <= "\u9fff" for char in f"{first_name}{last_name}"):
        return f"{last_name}{first_name}"
    return f"{first_name} {last_name}"


def _user_context_from_state(state: dict):
    return user_context_from_state(state, default_role="underwriter")


@tool
async def uw_deterministic_assessment(
    application_id: int,
    proposed_monthly_payment: float,
    state: Annotated[dict, InjectedState],
) -> str:
    """确定性计算 DTI/LTV，并核验三类材料和跨材料一致性。

    该工具只能输出人工审批辅助建议，不会自动批准或拒绝。
    """
    user = _user_context_from_state(state)
    trace_id = state.get("trace_id") or state.get("session_id") or f"assessment-{application_id}"
    async with SessionLocal() as session:
        result = await run_deterministic_assessment(
            session,
            user,
            application_id,
            proposed_monthly_payment=proposed_monthly_payment,
            trace_id=trace_id,
        )
    if result is None:
        return f"申请 #{application_id} 不存在或当前用户无权访问。"

    lines = [
        f"申请 #{application_id} 确定性授信辅助评估",
        f"DTI：{result.dti.value if result.dti.value is not None else '无法计算'}%",
        f"LTV：{result.ltv.value if result.ltv.value is not None else '无法计算'}%",
        f"材料完整：{'是' if result.documents.is_complete else '否'}",
        f"一致性状态：{result.consistency_status}",
        f"辅助建议：{result.suggestion}",
        "依据：",
    ]
    lines.extend(f"- {item}" for item in result.rationale)
    lines.extend(["", f"人工确认要求：{result.confirmation_instruction}"])
    return "\n".join(lines)


@tool
async def uw_queue_view(
    state: Annotated[dict, InjectedState],
) -> str:
    """View the underwriting queue sorted by urgency.

    Shows all applications currently in the underwriting stage with
    borrower names, loan amounts, assigned LO, days in queue, rate lock
    status, and urgency indicators.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        applications, total = await list_applications(
            session,
            user,
            filter_stage=ApplicationStage.UNDERWRITING,
            limit=50,
        )

        if total == 0:
            await write_audit_event(
                session,
                event_type="data_access",
                user_id=user.user_id,
                user_role=user.role.value,
                event_data={"action": "underwriter_queue_view", "result_count": 0},
            )
            await session.commit()
            return "当前授信审批队列中没有待处理申请。"

        urgency_map = await compute_urgency(session, applications)

        # Sort by urgency level (critical first)
        def sort_key(a):
            indicator = urgency_map.get(a.id)
            return _URGENCY_ORDER.get(indicator.level, 99) if indicator else 99

        applications.sort(key=sort_key)

        lines = [f"授信审批队列（共 {total} 笔）：", ""]
        for app in applications:
            indicator = urgency_map.get(app.id)
            urgency_label = _URGENCY_LABELS.get(indicator.level, "常规") if indicator else "常规"
            days = indicator.days_in_stage if indicator else 0

            # Borrower name(s)
            borrower_names = []
            for ab in app.application_borrowers or []:
                if ab.borrower:
                    borrower_names.append(
                        _person_name(ab.borrower.first_name, ab.borrower.last_name)
                    )
            names = "、".join(borrower_names) if borrower_names else "姓名待补充"

            loan_amt = f"¥{app.loan_amount:,.0f}" if app.loan_amount else "金额待补充"
            prop = app.property_address or "房产地址待补充"
            lo = app.assigned_to or "未分配"

            line = (
                f"- 申请 #{app.id}：{names}｜{loan_amt}｜{prop}｜"
                f"客户经理：{lo}｜队列时长：{days} 天｜优先级：{urgency_label}"
            )

            if indicator and indicator.factors:
                line += f" ({', '.join(indicator.factors)})"

            lines.append(line)

        await write_audit_event(
            session,
            event_type="data_access",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={
                "action": "underwriter_queue_view",
                "result_count": total,
            },
        )
        await session.commit()
        return "\n".join(lines)


def _format_application_detail(
    application_id: int,
    app,
    financials,
    documents,
    doc_total: int,
    conditions,
    rate_lock,
    risk_assessment=None,
) -> str:
    """Format application detail view into text.

    Pure function -- no DB access.
    """
    stage = app.stage.value if app.stage else "inquiry"
    lines = [
        f"申请 #{application_id}——授信审批详情",
        f"办理阶段：{format_enum_label(stage)}",
        "",
    ]

    # Borrower Profile
    lines.append("客户资料：")
    for ab in app.application_borrowers or []:
        if ab.borrower:
            b = ab.borrower
            role_label = "主借款人" if ab.is_primary else "共同借款人"
            lines.append(f"  {role_label}：{_person_name(b.first_name, b.last_name)}（{b.email}）")
            if b.employment_status:
                emp = (
                    b.employment_status.value
                    if hasattr(b.employment_status, "value")
                    else str(b.employment_status)
                )
                lines.append(f"    就业状态：{format_enum_label(emp)}")

    # Financial Summary
    lines.append("")
    lines.append("财务情况：")
    if financials:
        total_income = sum((f.gross_monthly_income or 0) for f in financials)
        total_debts = sum((f.monthly_debts or 0) for f in financials)
        total_assets = sum((f.total_assets or 0) for f in financials)
        credit_scores = [f.credit_score for f in financials if f.credit_score]
        min_credit = min(credit_scores) if credit_scores else None

        lines.append(f"  家庭月收入：¥{total_income:,.2f}")
        lines.append(f"  现有月负债：¥{total_debts:,.2f}")
        if total_income > 0:
            existing_debt_ratio = float(total_debts) / float(total_income) * 100
            lines.append(f"  现有负债率（不含拟贷款月供，仅供参考）：{existing_debt_ratio:.2f}%")
        lines.append(f"  资产合计：¥{total_assets:,.2f}")
        if min_credit is not None:
            lines.append(f"  最低模拟征信评分：{min_credit}")
    else:
        lines.append("  暂无财务数据。")

    # Use the persisted deterministic record as the single source of truth for
    # DTI.  The current-debt ratio above is deliberately not labelled DTI,
    # because DTI in this workflow includes the proposed housing payment.
    lines.append("")
    if risk_assessment and risk_assessment.dti_value is not None:
        dti_inputs = (risk_assessment.calculation_inputs or {}).get("dti", {})
        monthly_income = float(dti_inputs.get("monthly_income") or 0)
        existing_debt = float(dti_inputs.get("existing_monthly_debt") or 0)
        proposed_payment = float(dti_inputs.get("proposed_monthly_payment") or 0)
        total_obligations = existing_debt + proposed_payment
        lines.extend(
            [
                "最近一次固定规则评估：",
                "  指标口径：总债务收入比（DTI，含拟贷款月供）",
                f"  家庭月收入：¥{monthly_income:,.2f}",
                f"  现有月负债：¥{existing_debt:,.2f}",
                f"  拟贷款月供：¥{proposed_payment:,.2f}",
                f"  合计月偿付额：¥{total_obligations:,.2f}",
                f"  DTI：{float(risk_assessment.dti_value):.2f}%",
                "  公式：（现有月负债 + 拟贷款月供）/ 家庭月收入 × 100%",
            ]
        )
        if risk_assessment.dti_rating:
            lines.append(f"  风险等级：{format_enum_label(str(risk_assessment.dti_rating))}")
        lines.append("  数据来源：最近一次已保存的固定规则评估记录。")
    else:
        lines.append("固定规则评估：尚未生成，当前仅可查看现有负债率。")

    # Loan Details
    lines.append("")
    lines.append("贷款信息：")
    if app.loan_type:
        lines.append(
            f"  贷款类型：{_LOAN_TYPE_LABELS.get(app.loan_type.value, app.loan_type.value)}"
        )
    if app.loan_amount:
        lines.append(f"  贷款金额：¥{app.loan_amount:,.2f}")
    if app.property_value:
        lines.append(f"  房产价值：¥{app.property_value:,.2f}")
        if app.loan_amount and app.property_value:
            ltv = float(app.loan_amount) / float(app.property_value) * 100
            lines.append(f"  贷款成数：{ltv:.1f}%")
    if app.property_address:
        lines.append(f"  房产地址：{app.property_address}")

    # Documents
    lines.append("")
    if doc_total > 0:
        lines.append(f"申请材料（{doc_total} 项）：")
        for doc in documents:
            doc_type = doc.doc_type.value if hasattr(doc.doc_type, "value") else str(doc.doc_type)
            status_val = doc.status.value if hasattr(doc.status, "value") else str(doc.status)
            line = (
                f"  - [{doc.id}] {_DOC_TYPE_LABELS.get(doc_type, format_enum_label(doc_type))}："
                f"{format_enum_label(status_val)}"
            )
            if doc.quality_flags:
                line += f"（质量提示：{doc.quality_flags}）"
            lines.append(line)
    else:
        lines.append("申请材料：暂无。")

    # Conditions
    lines.append("")
    if conditions:
        lines.append(f"审批条件（{len(conditions)} 项）：")
        for c in conditions:
            status_val = c.get("status", "")
            desc = c.get("description", "")
            severity = c.get("severity", "")
            lines.append(
                f"  - [{format_enum_label(status_val)}] {desc}（{format_enum_label(severity)}）"
            )
    elif conditions is not None:
        lines.append("审批条件：暂无。")
    else:
        lines.append("审批条件：暂时无法加载。")

    # Rate Lock
    lines.append("")
    if rate_lock:
        rl_status = rate_lock.get("status", "none")
        if rl_status == "none":
            lines.append("执行利率：尚未锁定。")
        else:
            lines.append("执行利率：")
            lines.append(f"  状态：{_RATE_STATUS_LABELS.get(rl_status, rl_status)}")
            if rate_lock.get("locked_rate") is not None:
                lines.append(f"  利率：{rate_lock['locked_rate']:.3f}%")
            if rate_lock.get("expiration_date"):
                days = rate_lock.get("days_remaining", 0)
                lines.append(f"  有效期至：{rate_lock['expiration_date'][:10]}（剩余 {days} 天）")
            if rate_lock.get("is_urgent"):
                lines.append("  提醒：执行利率将在 7 天内到期，请优先处理。")
    else:
        lines.append("执行利率：暂时无法加载。")

    return "\n".join(lines)


@tool
async def uw_application_detail(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Get a detailed view of a loan application for underwriting review.

    Includes borrower profile, financial summary, loan details, documents
    with quality flags, conditions, and rate lock status.

    Args:
        application_id: The loan application ID to inspect.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return "未找到该申请，或您没有查看权限。"

        # Financials -- separate query (session-per-tool isolation pattern)
        financials = await get_financials(session, application_id)

        documents, doc_total = await list_documents(session, user, application_id, limit=50)
        conditions = await get_conditions(session, user, application_id)
        rate_lock = await get_rate_lock_status(session, user, application_id)
        risk_assessment = await get_latest_risk_assessment(session, application_id)

        # Format output before commit to avoid expired-attribute errors
        output = _format_application_detail(
            application_id,
            app,
            financials,
            documents,
            doc_total,
            conditions,
            rate_lock,
            risk_assessment,
        )

        await write_audit_event(
            session,
            event_type="data_access",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={"action": "underwriter_detail_view"},
        )
        await session.commit()
        return output


# Loan type -> term in months mapping
_LOAN_TERM_MAP = {
    "conventional_30": 360,
    "conventional_15": 180,
    "fha": 360,
    "va": 360,
    "jumbo": 360,
    "usda": 360,
    "arm": 360,
}


@tool
async def uw_predict_loan_approval(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Run the external predictive ML model on a loan application.

    Maps application data to the model's input fields and returns the
    prediction. Returns unavailability message when the model is not
    configured.

    Args:
        application_id: The loan application ID.
    """
    if not is_predictive_model_available():
        return "外部预测模型未配置；请使用确定性计算和人工审批流程。"

    predictive_tool = get_predictive_tool()
    if predictive_tool is None:
        return "外部预测模型工具不可用；请使用确定性计算和人工审批流程。"

    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return "未找到该申请，或您没有查看权限。"

        financials = await get_financials(session, application_id)

        # Aggregate financials across all borrowers
        total_income = sum((f.gross_monthly_income or 0) for f in financials) if financials else 0
        total_assets = sum((f.total_assets or 0) for f in financials) if financials else 0
        credit_scores = [f.credit_score for f in financials if f.credit_score] if financials else []
        min_credit = min(credit_scores) if credit_scores else 0

        # Derive employment status
        emp_statuses = []
        for ab in app.application_borrowers or []:
            if ab.borrower and ab.borrower.employment_status:
                emp_statuses.append(ab.borrower.employment_status.value)
        is_self_employed = "self_employed" in emp_statuses

        # Derive loan term from loan type
        loan_type_val = app.loan_type.value if app.loan_type else "conventional_30"
        loan_term = _LOAN_TERM_MAP.get(loan_type_val, 360)

        # Synthesize missing fields using application_id for variation
        app_hash = hash(application_id)
        no_of_dependents = abs(app_hash) % 5
        graduated = abs(app_hash) % 2 == 0

        # Split total assets across 4 categories (40/10/20/30)
        residential_assets = float(total_assets) * 0.4
        commercial_assets = float(total_assets) * 0.1
        luxury_assets = float(total_assets) * 0.2
        bank_assets = float(total_assets) * 0.3

        # Capture loan_amount before session closes (commit expires ORM objects)
        loan_amount = float(app.loan_amount or 0)

        await write_audit_event(
            session,
            event_type="agent_tool_called",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={"tool": "uw_predict_loan_approval"},
        )
        await session.commit()

    invoke_args = {
        "no_of_dependents": no_of_dependents,
        "graduated": graduated,
        "self_employed": is_self_employed,
        "income_annum": float(total_income) * 12,
        "loan_amount": loan_amount,
        "loan_term": loan_term,
        "cibil_score": min_credit,
        "residential_assets_value": residential_assets,
        "commercial_assets_value": commercial_assets,
        "luxury_assets_value": luxury_assets,
        "bank_asset_value": bank_assets,
    }
    # Invoke the external MCP tool
    try:
        result = await predictive_tool.ainvoke(invoke_args)
        result_text = str(result).strip()
        normalized = result_text.lower()
        if "rejected" in normalized or "denied" in normalized:
            outcome = "倾向未通过"
        elif "approved" in normalized:
            outcome = "倾向通过"
        else:
            return "外部预测模型返回了无法标准化的结果，请转人工复核。"
        return (
            f"外部预测模型辅助结果：{outcome}。该结果仅供风险复核参考，"
            "不得替代确定性规则检查和有权审批人员的最终决定。"
        )
    except Exception as e:
        logger.exception("Predictive model call failed for app %s", application_id)
        return f"外部预测模型调用失败：{e}。请转人工复核。"


@tool
async def uw_save_risk_assessment(
    application_id: int,
    dti_value: float | None,
    dti_rating: str | None,
    ltv_value: float | None,
    ltv_rating: str | None,
    credit_value: int | None,
    credit_rating: str | None,
    credit_source: str,
    income_stability_value: str | None,
    income_stability_rating: str | None,
    asset_sufficiency_value: float | None,
    asset_sufficiency_rating: str | None,
    overall_risk: str | None,
    recommendation: str,
    rationale: list[str] | None,
    conditions: list[str] | None,
    compensating_factors: list[str] | None,
    warnings: list[str] | None,
    predictive_model_result: str | None = None,
    predictive_model_available: bool | None = None,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Save a completed risk assessment to the database.

    Call this after computing all risk factors and the recommendation
    using the individual MCP risk tools. Persists the assessment and
    writes an audit event.

    Args:
        application_id: The loan application ID.
        dti_value: Computed DTI percentage (or null if unavailable).
        dti_rating: DTI risk rating (Low/Medium/High or null).
        ltv_value: Computed LTV percentage (or null if unavailable).
        ltv_rating: LTV risk rating (Low/Medium/High or null).
        credit_value: Credit score used (or null if unavailable).
        credit_rating: Credit risk rating (Low/Medium/High or null).
        credit_source: 'bureau_hard_pull' or 'self_reported'.
        income_stability_value: Employment status summary (or null).
        income_stability_rating: Income stability rating (Low/Medium/High or null).
        asset_sufficiency_value: Asset ratio percentage (or null).
        asset_sufficiency_rating: Asset sufficiency rating (Low/Medium/High or null).
        overall_risk: Overall risk rating (Low/Medium/High or null).
        recommendation: Approve, Approve with Conditions, Suspend, or Deny.
        rationale: List of reasons for the recommendation.
        conditions: List of conditions (if Approve with Conditions).
        compensating_factors: List of compensating factors found.
        warnings: List of data quality warnings.
        predictive_model_result: ML model prediction (Loan approved/rejected or null).
        predictive_model_available: Whether the predictive model was available.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return "未找到该申请，或您没有查看权限。"

        if app.stage != ApplicationStage.UNDERWRITING:
            stage_val = app.stage.value if app.stage else "unknown"
            await write_audit_event(
                session,
                event_type="agent_tool_called",
                user_id=user.user_id,
                user_role=user.role.value,
                application_id=application_id,
                event_data={
                    "tool": "uw_save_risk_assessment",
                    "error": f"wrong_stage:{stage_val}",
                },
            )
            await session.commit()
            return (
                f"风险辅助评估只能在授信审批阶段保存。申请 #{application_id} 当前处于"
                f"“{format_enum_label(stage_val)}”阶段。"
            )

        await create_risk_assessment(
            session,
            application_id=application_id,
            dti_value=dti_value,
            dti_rating=dti_rating,
            ltv_value=ltv_value,
            ltv_rating=ltv_rating,
            credit_value=credit_value,
            credit_rating=credit_rating,
            credit_source=credit_source,
            income_stability_value=income_stability_value,
            income_stability_rating=income_stability_rating,
            asset_sufficiency_value=asset_sufficiency_value,
            asset_sufficiency_rating=asset_sufficiency_rating,
            compensating_factors=compensating_factors or None,
            warnings=warnings or None,
            overall_risk=overall_risk,
            assessed_by=user.user_id,
            recommendation=recommendation,
            recommendation_rationale=rationale or None,
            recommendation_conditions=conditions or None,
            predictive_model_result=predictive_model_result,
            predictive_model_available=predictive_model_available,
        )

        await write_audit_event(
            session,
            event_type="agent_tool_called",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "tool": "uw_save_risk_assessment",
                "dti": dti_value,
                "ltv": ltv_value,
                "credit": credit_value,
                "credit_source": credit_source,
                "recommendation": recommendation,
                "predictive_model_result": predictive_model_result,
            },
        )
        await session.commit()

    return f"申请 #{application_id} 的风险辅助评估已保存。流程建议：{recommendation}。"


@tool
async def uw_preliminary_recommendation(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Re-evaluate the preliminary recommendation for an application.

    Args:
        application_id: The loan application ID to evaluate.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return "未找到该申请，或您没有查看权限。"

        if app.stage != ApplicationStage.UNDERWRITING:
            stage_val = app.stage.value if app.stage else "unknown"
            await write_audit_event(
                session,
                event_type="agent_tool_called",
                user_id=user.user_id,
                user_role=user.role.value,
                application_id=application_id,
                event_data={
                    "tool": "uw_preliminary_recommendation",
                    "error": f"wrong_stage:{stage_val}",
                },
            )
            await session.commit()
            return (
                f"初步辅助建议只能在授信审批阶段生成。申请 #{application_id} 当前处于"
                f"“{format_enum_label(stage_val)}”阶段。"
            )

        financials = await get_financials(session, application_id)

        # Prefer bureau credit score from hard-pull CreditReport
        bureau_score = None
        cr_result = await session.execute(
            select(CreditReport)
            .where(
                CreditReport.application_id == application_id,
                CreditReport.pull_type == "hard",
            )
            .order_by(CreditReport.pulled_at.desc())
            .limit(1)
        )
        hard_pull = cr_result.scalars().first()
        if hard_pull:
            bureau_score = hard_pull.credit_score

        _documents, doc_total = await list_documents(session, user, application_id, limit=50)
        borrowers = extract_borrower_info(app)
        risk = compute_risk_factors(app, financials, borrowers, bureau_credit_score=bureau_score)
        rec = compute_recommendation(
            risk,
            borrowers,
            has_financials=bool(financials),
            doc_total=doc_total,
        )

        # Persist recommendation on the latest risk assessment
        await update_recommendation(
            session,
            application_id,
            recommendation=rec.recommendation,
            rationale=rec.rationale or None,
            conditions=rec.conditions or None,
            assessed_by=user.user_id,
        )

        # Audit
        await write_audit_event(
            session,
            event_type="agent_tool_called",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "tool": "uw_preliminary_recommendation",
                "recommendation": rec.recommendation,
            },
        )
        await session.commit()

    # Format output
    lines = [
        f"申请 #{application_id} 初步辅助建议",
        "",
        f"流程建议：{rec.recommendation}",
        "",
    ]

    if rec.rationale:
        lines.append("建议依据：")
        for r in rec.rationale:
            lines.append(f"  - {r}")
        lines.append("")

    if rec.conditions:
        lines.append("待核验事项：")
        for i, c in enumerate(rec.conditions, 1):
            lines.append(f"  {i}. {c}")
        lines.append("")

    if risk.compensating_factors:
        lines.append("补充参考因素：")
        for cf in risk.compensating_factors:
            lines.append(f"  + {cf}")
        lines.append("")

    lines.append(
        "提示：本结果仅为授信辅助建议，不构成正式授信决定。最终结论必须由有权"
        "审批人员核验材料、适用政策和风险后作出；演示规则不替代金融机构正式制度。"
    )

    return "\n".join(lines)
