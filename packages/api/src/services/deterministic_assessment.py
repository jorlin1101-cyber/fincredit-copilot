# This project was developed with assistance from AI tools.
"""Deterministic Chinese-demo credit metrics with an explicit human decision boundary."""

from dataclasses import dataclass
from datetime import UTC, datetime

from db import Document, RiskAssessmentRecord
from db.enums import DocumentStatus, DocumentType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.auth import UserContext
from ..schemas.deterministic_assessment import (
    DeterministicAssessmentResponse,
    DocumentGate,
    RiskMetric,
)
from .application import get_application, get_financials
from .audit import write_audit_event
from .consistency import run_consistency_check

ASSESSMENT_RULE_VERSION = "DEMO-RISK-2026.08-v1"
RULE_VERSIONS = {
    "dti": "dti-proposed-payment-v1",
    "ltv": "ltv-loan-to-property-v1",
    "documents": "p0-three-documents-v1",
    "suggestion": ASSESSMENT_RULE_VERSION,
}

_P0_DOCUMENTS = {
    DocumentType.ID_CARD: "身份证",
    DocumentType.INCOME_CERTIFICATE: "收入证明",
    DocumentType.BANK_STATEMENT: "银行流水",
}
_USABLE_STATUSES = {
    DocumentStatus.PROCESSING_COMPLETE,
    DocumentStatus.PENDING_REVIEW,
    DocumentStatus.ACCEPTED,
}


@dataclass
class AssessmentComputation:
    dti: RiskMetric
    ltv: RiskMetric
    suggestion: str
    rationale: list[str]


def calculate_dti(
    monthly_income: float,
    existing_monthly_debt: float,
    proposed_monthly_payment: float,
) -> RiskMetric:
    """Calculate DTI from explicit numeric inputs; never ask an LLM to do arithmetic."""
    inputs = {
        "monthly_income": round(monthly_income, 2),
        "existing_monthly_debt": round(existing_monthly_debt, 2),
        "proposed_monthly_payment": round(proposed_monthly_payment, 2),
    }
    if monthly_income <= 0:
        return RiskMetric(
            value=None,
            rating=None,
            formula="(现有月负债 + 拟贷款月供) / 家庭月收入 × 100%",
            inputs=inputs,
            rule_version=RULE_VERSIONS["dti"],
        )
    value = round((existing_monthly_debt + proposed_monthly_payment) / monthly_income * 100, 2)
    rating = "Low" if value <= 40 else ("Medium" if value <= 50 else "High")
    return RiskMetric(
        value=value,
        rating=rating,
        formula="(现有月负债 + 拟贷款月供) / 家庭月收入 × 100%",
        inputs=inputs,
        rule_version=RULE_VERSIONS["dti"],
    )


def calculate_ltv(loan_amount: float, property_value: float) -> RiskMetric:
    """Calculate LTV and apply synthetic review bands, not an approval limit."""
    inputs = {
        "loan_amount": round(loan_amount, 2),
        "property_value": round(property_value, 2),
    }
    if loan_amount <= 0 or property_value <= 0:
        return RiskMetric(
            value=None,
            rating=None,
            formula="贷款金额 / 房产价值 × 100%",
            inputs=inputs,
            rule_version=RULE_VERSIONS["ltv"],
        )
    value = round(loan_amount / property_value * 100, 2)
    rating = "Low" if value <= 70 else ("Medium" if value <= 85 else "High")
    return RiskMetric(
        value=value,
        rating=rating,
        formula="贷款金额 / 房产价值 × 100%",
        inputs=inputs,
        rule_version=RULE_VERSIONS["ltv"],
    )


def build_document_gate(documents: list[Document]) -> DocumentGate:
    """Require exactly the three P0 Chinese evidence categories."""
    provided_types = {
        document.doc_type
        for document in documents
        if document.doc_type in _P0_DOCUMENTS and document.status in _USABLE_STATUSES
    }
    pending_types = {
        document.doc_type
        for document in documents
        if document.doc_type in _P0_DOCUMENTS
        and (document.status == DocumentStatus.PENDING_REVIEW or bool(document.quality_flags))
    }
    missing_types = set(_P0_DOCUMENTS) - provided_types
    return DocumentGate(
        required=list(_P0_DOCUMENTS.values()),
        provided=[_P0_DOCUMENTS[item] for item in _P0_DOCUMENTS if item in provided_types],
        missing=[_P0_DOCUMENTS[item] for item in _P0_DOCUMENTS if item in missing_types],
        pending_human_review=[
            _P0_DOCUMENTS[item] for item in _P0_DOCUMENTS if item in pending_types
        ],
        is_complete=not missing_types,
    )


def derive_suggestion(
    dti: RiskMetric,
    ltv: RiskMetric,
    documents: DocumentGate,
    consistency_status: str,
    *,
    proposed_monthly_payment: float,
) -> tuple[str, list[str]]:
    """Return a workflow suggestion only; approval/denial is intentionally impossible."""
    rationale: list[str] = []
    if dti.value is not None:
        rationale.append(f"DTI 为 {dti.value:.2f}%，复核关注级别：{dti.rating}。")
    else:
        rationale.append("缺少有效家庭月收入，无法计算 DTI。")
    if ltv.value is not None:
        rationale.append(f"LTV 为 {ltv.value:.2f}%，复核关注级别：{ltv.rating}。")
    else:
        rationale.append("缺少贷款金额或房产价值，无法计算 LTV。")

    if documents.missing:
        rationale.append(f"缺少 P0 必需材料：{'、'.join(documents.missing)}。")
        suggestion = "NEEDS_SUPPLEMENT"
    elif (
        dti.value is None
        or ltv.value is None
        or proposed_monthly_payment <= 0
        or consistency_status != "passed"
        or bool(documents.pending_human_review)
        or "High" in {dti.rating, ltv.rating}
    ):
        suggestion = "NEEDS_MANUAL_REVIEW"
    else:
        suggestion = "READY_FOR_HUMAN_DECISION"

    if proposed_monthly_payment <= 0:
        rationale.append("未提供拟贷款月供，DTI 仅反映现有负债，须补充后复核。")
    if consistency_status != "passed":
        rationale.append(f"跨材料一致性状态为 {consistency_status}，须查看证据并人工处理。")
    if documents.pending_human_review:
        rationale.append(f"存在待人工确认材料：{'、'.join(documents.pending_human_review)}。")
    rationale.append("以上仅为确定性辅助建议，不是批准或拒绝；最终决策须由有权人员确认。")
    return suggestion, rationale


async def run_deterministic_assessment(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
    *,
    proposed_monthly_payment: float,
    trace_id: str,
) -> DeterministicAssessmentResponse | None:
    """Load evidence, calculate metrics, persist inputs/results and append audit evidence."""
    application = await get_application(session, user, application_id)
    if application is None:
        return None

    financials = await get_financials(session, application_id)
    monthly_income = sum(float(item.gross_monthly_income or 0) for item in financials)
    existing_debt = sum(float(item.monthly_debts or 0) for item in financials)
    loan_amount = float(application.loan_amount or 0)
    property_value = float(application.property_value or 0)

    document_result = await session.execute(
        select(Document).where(
            Document.application_id == application_id,
            Document.doc_type.in_(list(_P0_DOCUMENTS)),
        )
    )
    documents = list(document_result.scalars().all())
    document_gate = build_document_gate(documents)

    consistency = await run_consistency_check(session, user, application_id)
    consistency_status = consistency.status if consistency else "insufficient_data"
    consistency_issue_count = len(consistency.issues) if consistency else 0

    dti = calculate_dti(monthly_income, existing_debt, proposed_monthly_payment)
    ltv = calculate_ltv(loan_amount, property_value)
    suggestion, rationale = derive_suggestion(
        dti,
        ltv,
        document_gate,
        consistency_status,
        proposed_monthly_payment=proposed_monthly_payment,
    )
    risk_order = {None: 0, "Low": 1, "Medium": 2, "High": 3}
    overall_rating = max((dti.rating, ltv.rating), key=lambda item: risk_order[item])
    calculated_at = datetime.now(UTC)

    record = RiskAssessmentRecord(
        application_id=application_id,
        dti_value=dti.value,
        dti_rating=dti.rating,
        ltv_value=ltv.value,
        ltv_rating=ltv.rating,
        overall_risk=overall_rating,
        recommendation=suggestion,
        recommendation_rationale=rationale,
        recommendation_conditions=document_gate.missing,
        rule_version=ASSESSMENT_RULE_VERSION,
        calculation_inputs={"dti": dti.inputs, "ltv": ltv.inputs},
        rule_results={"dti": dti.model_dump(), "ltv": ltv.model_dump()},
        document_completeness=document_gate.model_dump(),
        consistency_result=(consistency.model_dump(mode="json") if consistency else None),
        human_review_required=True,
        trace_id=trace_id,
        assessed_by=user.user_id,
    )
    session.add(record)
    await session.flush()

    response = DeterministicAssessmentResponse(
        id=record.id,
        application_id=application_id,
        trace_id=trace_id,
        calculated_at=calculated_at,
        dti=dti,
        ltv=ltv,
        documents=document_gate,
        consistency_status=consistency_status,
        consistency_issue_count=consistency_issue_count,
        suggestion=suggestion,
        rationale=rationale,
        human_review_required=True,
        confirmation_instruction=(
            "审批 Agent 只能生成决策提案；有权审批人员查看证据并明确确认后，方可写入最终决策。"
        ),
        rule_versions=RULE_VERSIONS,
    )
    await write_audit_event(
        session,
        event_type="deterministic_risk_assessment",
        session_id=trace_id,
        user_id=user.user_id,
        user_role=user.role.value,
        application_id=application_id,
        event_data=response.model_dump(mode="json"),
    )
    await session.commit()
    return response
