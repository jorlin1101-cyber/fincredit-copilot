# This project was developed with assistance from AI tools.
"""LangGraph tool for China housing-credit compliance review.

Wraps the pure compliance check functions with DB access to gather
application data, then formats results for the underwriter agent.

Design note -- session-per-tool-call:
    Each tool opens its own ``SessionLocal()`` context rather than sharing
    a single session across the agent turn.  See underwriter_tools.py
    for rationale.
"""

import logging
from datetime import date
from typing import Annotated

from db.database import SessionLocal
from db.enums import ApplicationStage, DocumentType
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from ..services.application import get_application, get_financials
from ..services.audit import write_audit_event
from ..services.compliance.china_checks import (
    check_housing_credit_policy,
    check_material_authenticity,
    check_repayment_ability,
    run_china_checks,
)
from ..services.compliance_result import create_compliance_result
from ..services.document import list_documents
from .shared import format_enum_label, user_context_from_state

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "\n提示：检查结果仅用于授信辅助演示，不构成法律、监管或最终授信意见；"
    "具体业务须由有权人员核验官方政策原文并完成审批。"
)

_IDENTITY_DOC_TYPES = frozenset(
    {DocumentType.ID_CARD, DocumentType.PASSPORT, DocumentType.DRIVERS_LICENSE}
)
_INCOME_DOC_TYPES = frozenset(
    {
        DocumentType.INCOME_CERTIFICATE,
        DocumentType.W2,
        DocumentType.PAY_STUB,
        DocumentType.TAX_RETURN,
    }
)
_ASSET_DOC_TYPES = frozenset({DocumentType.BANK_STATEMENT})

_TYPE_ALIASES = {
    "ECOA": "MATERIAL_REVIEW",
    "ATR_QM": "REPAYMENT_ABILITY",
    "TRID": "LOCAL_POLICY",
}


def _user_context_from_state(state: dict):
    return user_context_from_state(state, default_role="underwriter")


def _format_check_result(check) -> list[str]:
    """Format a single ComplianceCheckResult into output lines."""
    lines = [
        f"  状态：{check.status.value}",
        f"  说明：{check.rationale}",
    ]
    if check.details:
        lines.append("  核验明细：")
        for d in check.details:
            lines.append(f"    - {d}")
    return lines


@tool
async def compliance_check(
    application_id: int,
    regulation_type: str = "ALL",
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """对住房贷款申请执行中国场景的结构化合规辅助检查。

    Validates regulatory compliance for applications in the underwriting
    stage. Can run individual checks or all three combined.

    Args:
        application_id: 贷款申请编号。
        regulation_type: 检查类型：MATERIAL_REVIEW、REPAYMENT_ABILITY、
            LOCAL_POLICY 或 ALL。
    """
    user = _user_context_from_state(state)
    regulation_type = _TYPE_ALIASES.get(
        regulation_type.upper().strip(), regulation_type.upper().strip()
    )

    valid_types = {"MATERIAL_REVIEW", "REPAYMENT_ABILITY", "LOCAL_POLICY", "ALL"}
    if regulation_type not in valid_types:
        return (
            f"检查类型“{regulation_type}”无效。"
            f"可选值：{', '.join(sorted(valid_types))}。"
        )

    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return f"申请 #{application_id} 不存在或当前用户无权访问。"

        if app.stage != ApplicationStage.UNDERWRITING:
            stage_val = app.stage.value if app.stage else "unknown"
            await write_audit_event(
                session,
                event_type="agent_tool_called",
                user_id=user.user_id,
                user_role=user.role.value,
                application_id=application_id,
                event_data={
                    "tool": "compliance_check",
                    "error": f"wrong_stage:{stage_val}",
                },
            )
            await session.commit()
            return (
                f"结构化合规检查仅适用于授信审批阶段。申请 #{application_id} 当前处于"
                f"“{format_enum_label(stage_val)}”阶段。"
            )

        # Gather data for checks
        financials = await get_financials(session, application_id)

        documents, _ = await list_documents(session, user, application_id, limit=100)

        # Compute repayment-ability inputs.
        total_income = sum(float(f.gross_monthly_income or 0) for f in financials)
        total_debts = sum(float(f.monthly_debts or 0) for f in financials)
        dti = total_debts / total_income if total_income > 0 else None

        doc_types = set()
        for doc in documents:
            dt = doc.doc_type if hasattr(doc.doc_type, "value") else None
            if dt:
                doc_types.add(dt)

        has_identity_docs = bool(doc_types & _IDENTITY_DOC_TYPES)
        has_income_docs = bool(doc_types & _INCOME_DOC_TYPES)
        has_asset_docs = bool(doc_types & _ASSET_DOC_TYPES)

        # Run requested checks
        results = {}

        if regulation_type in ("MATERIAL_REVIEW", "ALL"):
            results["MATERIAL_REVIEW"] = check_material_authenticity(
                has_identity_docs=has_identity_docs,
                has_income_docs=has_income_docs,
                has_asset_docs=has_asset_docs,
            )

        if regulation_type in ("REPAYMENT_ABILITY", "ALL"):
            results["REPAYMENT_ABILITY"] = check_repayment_ability(
                dti=dti,
                has_income_docs=has_income_docs,
                has_asset_docs=has_asset_docs,
            )

        if regulation_type in ("LOCAL_POLICY", "ALL"):
            created_at = app.created_at.date() if app.created_at else date.today()
            results["LOCAL_POLICY"] = check_housing_credit_policy(
                loan_amount=app.loan_amount,
                property_value=app.property_value,
                application_date=created_at,
            )

        # Run combined if ALL
        combined = None
        if regulation_type == "ALL" and len(results) == 3:
            combined = run_china_checks(
                results["MATERIAL_REVIEW"],
                results["REPAYMENT_ABILITY"],
                results["LOCAL_POLICY"],
            )

        # Persist compliance result
        material = results.get("MATERIAL_REVIEW")
        repayment = results.get("REPAYMENT_ABILITY")
        policy = results.get("LOCAL_POLICY")
        # These legacy column names are retained to avoid an unsafe in-place
        # migration of existing demo data. Their user-visible meaning is mapped
        # to the three China-scenario checks above.
        await create_compliance_result(
            session,
            application_id=application_id,
            ecoa_status=material.status.value if material else None,
            ecoa_rationale=material.rationale if material else None,
            ecoa_details=material.details if material else None,
            atr_qm_status=repayment.status.value if repayment else None,
            atr_qm_rationale=repayment.rationale if repayment else None,
            atr_qm_details=repayment.details if repayment else None,
            trid_status=policy.status.value if policy else None,
            trid_rationale=policy.rationale if policy else None,
            trid_details=policy.details if policy else None,
            overall_status=combined["overall_status"].value if combined else None,
            can_proceed=combined["can_proceed"] if combined else None,
            checked_by=user.user_id,
        )

        # Audit
        audit_data = {
            "tool": "compliance_check",
            "regulation_type": regulation_type,
            "results": {k: v.status.value for k, v in results.items()},
        }
        if combined:
            audit_data["overall_status"] = combined["overall_status"].value
            audit_data["can_proceed"] = combined["can_proceed"]

        await write_audit_event(
            session,
            event_type="compliance_check",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data=audit_data,
        )
        await session.commit()

    # Format output
    lines = [f"申请 #{application_id} 合规辅助检查", ""]

    for check_result in results.values():
        lines.append(f"{check_result.regulation}:")
        lines.extend(_format_check_result(check_result))
        lines.append("")

    if combined:
        lines.append(f"综合状态：{combined['overall_status'].value}")
        can_proceed_text = "可进入人工审批" if combined["can_proceed"] else "不可继续，存在未解决项"
        lines.append(f"流程建议：{can_proceed_text}")
        lines.append("")

    lines.append(_DISCLAIMER)

    return "\n".join(lines)
