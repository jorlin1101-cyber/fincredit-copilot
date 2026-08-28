# This project was developed with assistance from AI tools.
"""LangGraph tools for the loan officer assistant agent.

These wrap existing services so the LO agent can review applications,
inspect documents, flag documents for resubmission, check underwriting
readiness, and submit applications to underwriting.

Design note -- session-per-tool-call:
    Each tool opens its own ``SessionLocal()`` context rather than sharing
    a single session across the agent turn.  This is intentional: LangGraph
    tool nodes run as independent async tasks and may execute in any order,
    so sharing a session would risk interleaved flushes, stale reads, and
    MissingGreenlet errors.  The per-tool pattern keeps each DB interaction
    self-contained and avoids cross-tool state leakage.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from db import Application, ApplicationBorrower, CreditReport, PrequalificationDecision
from db.database import SessionLocal
from db.enums import ApplicationStage, DocumentStatus
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..services.application import (
    InvalidTransitionError,
    get_application,
    get_financials,
    transition_stage,
)
from ..services.audit import write_audit_event
from ..services.calculator import compute_monthly_payment
from ..services.completeness import check_completeness, check_underwriting_readiness
from ..services.condition import get_conditions, parse_quality_flags
from ..services.credit_bureau import get_credit_bureau_service
from ..services.document import get_document, list_documents, update_document_status
from ..services.prequalification import evaluate_prequalification
from ..services.products import PRODUCTS
from ..services.rate_lock import get_rate_lock_status
from ..services.status import get_application_status
from .shared import user_context_from_state

_COMMUNICATION_TYPES = {
    "document_request",
    "condition_explanation",
    "status_update",
    "resubmission_notice",
}

_LOAN_TYPE_LABELS: dict[str, str] = {
    "conventional_30": "30年期个人住房贷款",
    "conventional_15": "15年期个人住房贷款",
    "fha": "首套住房贷款（兼容类型）",
    "va": "优待客群住房贷款（兼容类型）",
    "jumbo": "大额住房贷款",
    "usda": "县域住房贷款（兼容类型）",
    "arm": "利率调整型住房贷款",
}

_SEVERITY_LABELS: dict[str, str] = {
    "prior_to_approval": "审批前完成",
    "prior_to_docs": "合同文件出具前完成",
    "prior_to_closing": "放款签约前完成",
    "prior_to_funding": "放款前完成",
}

_COMM_TYPE_LABELS: dict[str, str] = {
    "document_request": "补件通知",
    "condition_explanation": "审批条件说明",
    "status_update": "进度更新",
    "resubmission_notice": "重新提交材料通知",
}

_STAGE_LABELS: dict[str, str] = {
    "inquiry": "咨询",
    "prequalification": "预审",
    "application": "申请中",
    "processing": "材料处理中",
    "underwriting": "授信审批",
    "conditional_approval": "有条件通过",
    "clear_to_close": "具备放款条件",
    "closed": "已结案",
    "denied": "未通过",
    "withdrawn": "已撤回",
}

_DOCUMENT_LABELS: dict[str, str] = {
    "id_card": "居民身份证",
    "income_certificate": "收入证明",
    "w2": "工资与税务证明（兼容材料）",
    "pay_stub": "近期工资单",
    "tax_return": "个人所得税纳税记录",
    "bank_statement": "银行流水",
    "drivers_license": "身份证明（兼容材料）",
    "passport": "护照",
    "property_appraisal": "房产评估报告",
    "homeowners_insurance": "房屋保险凭证",
    "title_insurance": "不动产权属证明",
    "flood_insurance": "相关保险凭证",
    "purchase_agreement": "购房合同",
    "gift_letter": "赠与资金说明",
    "other": "其他材料",
}

_DOCUMENT_STATUS_LABELS: dict[str, str] = {
    "uploaded": "已上传",
    "processing": "识别处理中",
    "processing_complete": "识别完成",
    "processing_failed": "识别失败",
    "pending_review": "待复核",
    "accepted": "已通过",
    "flagged_for_resubmission": "需重新提交",
    "rejected": "已驳回",
}


def _person_name(first_name: str, last_name: str) -> str:
    if any("\u4e00" <= char <= "\u9fff" for char in f"{first_name}{last_name}"):
        return f"{last_name}{first_name}"
    return f"{first_name} {last_name}"


def _user_context_from_state(state: dict):
    return user_context_from_state(state, default_role="loan_officer")


@tool
async def lo_pipeline_summary(
    state: Annotated[dict, InjectedState],
) -> str:
    """Get a summary of all applications in the loan officer's pipeline, grouped by stage.

    Returns counts per stage and a brief listing of each application.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        from ..services.scope import apply_data_scope

        stmt = (
            select(Application)
            .options(
                selectinload(Application.application_borrowers).joinedload(
                    ApplicationBorrower.borrower
                ),
            )
            .order_by(Application.updated_at.desc())
        )
        stmt = apply_data_scope(stmt, user.data_scope, user)
        result = await session.execute(stmt)
        apps = result.unique().scalars().all()

    if not apps:
        return "您的客户经理工作台当前没有贷款申请。"

    # Group by stage
    by_stage: dict[str, list] = {}
    for app in apps:
        stage_value = app.stage.value if app.stage else "inquiry"
        stage_label = _STAGE_LABELS.get(stage_value, stage_value)
        by_stage.setdefault(stage_label, []).append(app)

    lines = [f"客户经理工作台共有 {len(apps)} 笔申请。", ""]
    for stage_label, stage_apps in by_stage.items():
        lines.append(f"{stage_label} ({len(stage_apps)}):")
        for app in stage_apps:
            borrower_name = ""
            for ab in app.application_borrowers or []:
                if ab.is_primary and ab.borrower:
                    borrower_name = _person_name(ab.borrower.first_name, ab.borrower.last_name)
                    break
            amount_str = f"¥{app.loan_amount:,.0f}" if app.loan_amount else "金额待定"
            loan_label = _LOAN_TYPE_LABELS.get(app.loan_type.value if app.loan_type else "", "")
            parts = [f"  #{app.id}"]
            if borrower_name:
                parts.append(borrower_name)
            if loan_label:
                parts.append(loan_label)
            parts.append(amount_str)
            lines.append(" - ".join(parts))
        lines.append("")

    return "\n".join(lines)


@tool
async def lo_application_detail(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Get a detailed summary of a loan application including borrower info, financials, stage, documents, and conditions.

    Args:
        application_id: The loan application ID to review.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return "未找到该申请，或您没有查看权限。"

        status = await get_application_status(session, user, application_id)

    stage = app.stage.value if app.stage else "inquiry"
    lines = [
        f"申请 #{application_id} 当前情况：",
        f"办理阶段：{_STAGE_LABELS.get(stage, stage)}",
    ]

    if app.loan_type:
        lines.append(f"贷款类型：{_LOAN_TYPE_LABELS.get(app.loan_type.value, app.loan_type.value)}")
    if app.property_address:
        lines.append(f"房产地址：{app.property_address}")
    if app.loan_amount:
        lines.append(f"贷款金额：¥{app.loan_amount:,.2f}")
    if app.property_value:
        lines.append(f"房产价值：¥{app.property_value:,.2f}")

    # Borrower info
    for ab in app.application_borrowers or []:
        if ab.borrower:
            b = ab.borrower
            role_label = "主借款人" if ab.is_primary else "共同借款人"
            lines.append(f"{role_label}：{_person_name(b.first_name, b.last_name)}（{b.email}）")

    # Status summary
    if status:
        lines.append("")
        lines.append(
            f"申请材料：已提供 {status.provided_doc_count}/{status.required_doc_count} 项，"
            f"{'材料齐全' if status.is_document_complete else '仍需补充'}"
        )
        if status.open_condition_count > 0:
            lines.append(f"待处理审批条件：{status.open_condition_count} 项")
        if status.pending_actions:
            lines.append("下一步事项：")
            for action in status.pending_actions:
                lines.append(f"  - {action.description}")

    return "\n".join(lines)


@tool
async def lo_document_review(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """List all documents for an application with their status, quality flags, and upload date.

    Args:
        application_id: The loan application ID.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        documents, total = await list_documents(session, user, application_id, limit=50)

    if total == 0:
        return f"申请 #{application_id} 暂无已上传材料。"

    lines = [f"申请 #{application_id} 共有 {total} 份材料："]
    for doc in documents:
        doc_type = doc.doc_type.value if hasattr(doc.doc_type, "value") else str(doc.doc_type)
        status_val = doc.status.value if hasattr(doc.status, "value") else str(doc.status)
        line = (
            f"{doc.id}. {_DOCUMENT_LABELS.get(doc_type, doc_type)}："
            f"{_DOCUMENT_STATUS_LABELS.get(status_val, status_val)}"
        )

        if doc.quality_flags:
            flags = parse_quality_flags(doc.quality_flags)
            if flags:
                line += f"（质量提示：{'、'.join(flags)}）"

        if doc.created_at:
            line += f"（上传日期：{doc.created_at.strftime('%Y年%m月%d日')}）"
        lines.append(line)

    return "\n".join(lines)


@tool
async def lo_document_quality(
    application_id: int,
    document_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Get detailed quality information for a specific document.

    Args:
        application_id: The loan application ID.
        document_id: The document ID to inspect.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        doc = await get_document(session, user, document_id)

    if doc is None:
        return "未找到该材料，或您没有查看权限。"

    if doc.application_id != application_id:
        return "该材料不属于当前申请。"

    doc_type = doc.doc_type.value if hasattr(doc.doc_type, "value") else str(doc.doc_type)
    status_val = doc.status.value if hasattr(doc.status, "value") else str(doc.status)

    lines = [
        f"材料 #{document_id} 详情：",
        f"材料类型：{_DOCUMENT_LABELS.get(doc_type, doc_type)}",
        f"处理状态：{_DOCUMENT_STATUS_LABELS.get(status_val, status_val)}",
    ]

    if doc.quality_flags:
        flags = parse_quality_flags(doc.quality_flags)
        if flags:
            lines.append("质量提示：")
            for flag in flags:
                lines.append(f"  - {flag}")
        else:
            lines.append("材料质量：未发现明显问题")
    else:
        lines.append("材料质量：未发现明显问题")

    if doc.created_at:
        lines.append(f"上传时间：{doc.created_at.strftime('%Y年%m月%d日 %H:%M')}")

    return "\n".join(lines)


@tool
async def lo_completeness_check(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Check document completeness for an application from the loan officer's perspective.

    Args:
        application_id: The loan application ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await check_completeness(session, user, application_id)

    if result is None:
        return "未找到该申请，或您没有查看权限。"

    lines = [
        f"申请 #{application_id} 材料完整性：",
        f"结论：{'材料齐全' if result.is_complete else '仍需补充'}，"
        f"已提供 {result.provided_count}/{result.required_count} 项必需材料。",
        "",
    ]
    for req in result.requirements:
        status = "已提供" if req.is_provided else "缺失"
        line = f"{req.label}：{status}"
        if req.status:
            line += f"（{_DOCUMENT_STATUS_LABELS.get(req.status.value, req.status.value)}）"
        if req.quality_flags:
            line += f"（质量提示：{'、'.join(req.quality_flags)}）"
        lines.append(line)

    return "\n".join(lines)


@tool
async def lo_mark_resubmission(
    application_id: int,
    document_id: int,
    reason: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Flag a document for resubmission by the borrower, with a reason.

    Only documents that have been processed (PROCESSING_COMPLETE, PENDING_REVIEW,
    ACCEPTED, or REJECTED) can be flagged. The borrower will be notified to upload
    a replacement.

    Args:
        application_id: The loan application ID.
        document_id: The document ID to flag.
        reason: Explanation of why the document needs resubmission.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        try:
            doc = await update_document_status(
                session,
                user,
                application_id,
                document_id,
                DocumentStatus.FLAGGED_FOR_RESUBMISSION,
                reason=reason,
            )
        except ValueError as e:
            return f"无法更新材料状态：{e}"

        if doc is None:
            return "未找到该材料、材料不属于当前申请，或您没有操作权限。"

        await write_audit_event(
            session,
            event_type="document_flagged_for_resubmission",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "document_id": document_id,
                "reason": reason,
            },
        )
        await session.commit()

    return (
        f"材料 #{document_id} 已标记为需要重新提交。原因：{reason}。"
        "系统已记录该补件事项，等待客户重新上传。"
    )


@tool
async def lo_underwriting_readiness(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Check whether an application is ready to be submitted to underwriting.

    Reviews stage, document completeness, processing status, and quality
    flags. Returns a clear verdict with any blockers that must be resolved.

    Args:
        application_id: The loan application ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await check_underwriting_readiness(session, user, application_id)

    if result is None:
        return "未找到该申请，或您没有查看权限。"

    if result["is_ready"]:
        return (
            f"申请 #{application_id} 已具备提交授信审批的条件。"
            "必需材料已齐全并完成处理，未发现阻断性质量问题。是否确认提交？"
        )

    lines = [
        f"申请 #{application_id} 暂不具备提交授信审批的条件，原因如下：",
    ]
    for blocker in result["blockers"]:
        lines.append(f"  - {blocker}")
    lines.append("")
    lines.append("请先处理以上事项，再提交授信审批。")

    return "\n".join(lines)


@tool
async def lo_submit_to_underwriting(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Submit an application to underwriting.

    This performs a two-step stage transition: APPLICATION -> PROCESSING ->
    UNDERWRITING. The state machine requires PROCESSING as an intermediate
    stage. Both transitions are audited.

    Note: When the Processor persona is added in a future phase, this tool
    would only transition to PROCESSING; the Processor would then prep the
    loan file and submit to UNDERWRITING.

    Readiness is checked first -- if blockers exist, the submission is
    refused with details.

    Args:
        application_id: The loan application ID to submit.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        # Gate: check readiness
        readiness = await check_underwriting_readiness(session, user, application_id)
        if readiness is None:
            return "未找到该申请，或您没有查看权限。"

        if not readiness["is_ready"]:
            lines = ["暂时无法提交授信审批，仍有以下事项需要处理："]
            for b in readiness["blockers"]:
                lines.append(f"  - {b}")
            return "\n".join(lines)

        # Step 1: APPLICATION -> PROCESSING
        app = await transition_stage(session, user, application_id, ApplicationStage.PROCESSING)
        if app is None:
            return "提交失败：无法将申请转入材料处理阶段。"

        await write_audit_event(
            session,
            event_type="stage_transition",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "from_stage": "application",
                "to_stage": "processing",
                "action": "lo_submit_to_underwriting",
            },
        )

        # Step 2: PROCESSING -> UNDERWRITING
        app = await transition_stage(session, user, application_id, ApplicationStage.UNDERWRITING)
        if app is None:
            return "提交失败：无法将申请转入授信审批阶段。"

        await write_audit_event(
            session,
            event_type="stage_transition",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "from_stage": "processing",
                "to_stage": "underwriting",
                "action": "lo_submit_to_underwriting",
            },
        )
        await session.commit()

    return (
        f"申请 #{application_id} 已提交授信审批。当前阶段：授信审批。"
        "审批人员将复核申请，并在需要时提出补充条件。"
    )


@tool
async def lo_draft_communication(
    application_id: int,
    communication_type: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Gather comprehensive application context for drafting a borrower communication.

    Collects borrower info, loan details, document completeness, open conditions,
    and rate lock status in a single call. The LLM uses this context to compose
    the actual communication draft.

    Args:
        application_id: The loan application ID.
        communication_type: One of: document_request, condition_explanation,
            status_update, resubmission_notice.
    """
    if communication_type not in _COMMUNICATION_TYPES:
        valid = ", ".join(sorted(_COMMUNICATION_TYPES))
        return f"不支持的沟通类型“{communication_type}”。可用类型：{valid}"

    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return "未找到该申请，或您没有查看权限。"

        completeness = await check_completeness(session, user, application_id)
        conditions = await get_conditions(session, user, application_id, open_only=True)
        rate_lock = await get_rate_lock_status(session, user, application_id)

    # --- Header ---
    type_label = _COMM_TYPE_LABELS.get(communication_type, communication_type)
    lines = [
        f"申请 #{application_id} 沟通信息",
        f"沟通类型：{type_label}",
        "",
    ]

    # --- Borrower ---
    lines.append("客户信息：")
    for ab in app.application_borrowers or []:
        if ab.borrower:
            b = ab.borrower
            role_label = "主借款人" if ab.is_primary else "共同借款人"
            lines.append(f"  {role_label}：{_person_name(b.first_name, b.last_name)}（{b.email}）")

    # --- Loan details ---
    lines.append("")
    lines.append("贷款信息：")
    if app.property_address:
        lines.append(f"  房产地址：{app.property_address}")
    if app.loan_type:
        lt_val = app.loan_type.value if hasattr(app.loan_type, "value") else str(app.loan_type)
        lt_label = _LOAN_TYPE_LABELS.get(lt_val, lt_val)
        lines.append(f"  贷款类型：{lt_label}")
    if app.loan_amount:
        lines.append(f"  贷款金额：¥{app.loan_amount:,.2f}")
    stage = app.stage.value if app.stage else "inquiry"
    lines.append(f"  办理阶段：{_STAGE_LABELS.get(stage, stage)}")

    # --- Documents ---
    if completeness:
        provided = completeness.provided_count
        required = completeness.required_count
        lines.append("")
        lines.append(f"申请材料（已提供 {provided}/{required} 项）：")
        for req in completeness.requirements:
            if req.is_provided:
                status_val = req.status.value if req.status else "accepted"
                line = f"  {req.label}：已提供（{_DOCUMENT_STATUS_LABELS.get(status_val, status_val)}）"
                if req.quality_flags:
                    line += f"（质量提示：{'、'.join(req.quality_flags)}）"
            else:
                line = f"  {req.label}：缺失"
            lines.append(line)

    # --- Conditions ---
    if conditions:
        lines.append("")
        lines.append(f"待处理审批条件（{len(conditions)} 项）：")
        for c in conditions:
            sev = c.get("severity", "")
            sev_label = _SEVERITY_LABELS.get(sev, sev) if sev else ""
            desc = c.get("description", "")
            if sev_label:
                lines.append(f"  - [{sev_label}] {desc}")
            else:
                lines.append(f"  - {desc}")
    elif conditions is not None:
        lines.append("")
        lines.append("待处理审批条件（0 项）：")
        lines.append("  暂无")

    # --- Rate lock ---
    if rate_lock:
        lines.append("")
        lines.append("执行利率：")
        rl_status = rate_lock.get("status", "none")
        if rl_status == "none":
            lines.append("  暂无已确认的执行利率")
        else:
            lines.append(f"  状态：{rl_status}")
            if rate_lock.get("locked_rate") is not None:
                lines.append(f"  利率：{rate_lock['locked_rate']:.3f}%")
            if rate_lock.get("expiration_date"):
                days = rate_lock.get("days_remaining", 0)
                lines.append(f"  有效期至：{rate_lock['expiration_date'][:10]}（剩余 {days} 天）")
            if rate_lock.get("is_urgent"):
                lines.append("  提醒：执行利率将在 7 天内到期，请优先处理。")

    # HMDA exclusion reminder
    lines.append("")
    lines.append("合规提醒：沟通内容不得包含与贷款办理无关的敏感个人属性信息。")

    return "\n".join(lines)


@tool
async def lo_send_communication(
    application_id: int,
    communication_type: str,
    subject: str,
    recipient_name: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Record that a borrower communication was sent (audit only -- no actual email delivery at MVP).

    Call this only after the loan officer has reviewed and approved the draft.

    Args:
        application_id: The loan application ID.
        communication_type: One of: document_request, condition_explanation,
            status_update, resubmission_notice.
        subject: The subject line of the communication.
        recipient_name: The borrower's name.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return "Application not found or you don't have access to it."

        await write_audit_event(
            session,
            event_type="communication_sent",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "communication_type": communication_type,
                "subject": subject,
                "recipient_name": recipient_name,
                "delivery_method": "audit_only",
            },
        )
        await session.commit()

    return (
        f"Communication recorded: '{subject}' to {recipient_name} "
        f"for application #{application_id}. "
        "(MVP: audit log only -- no email delivery.)"
    )


_VALID_PRODUCT_IDS = {p.id for p in PRODUCTS}


@tool
async def lo_pull_credit(
    application_id: int,
    pull_type: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Pull credit for the primary borrower on a loan application.

    Performs a simulated soft or hard credit pull and stores the result.
    Soft pulls are used for pre-qualification; hard pulls for underwriting.

    Args:
        application_id: The loan application ID.
        pull_type: "soft" or "hard".
    """
    if pull_type not in ("soft", "hard"):
        return "Invalid pull_type. Must be 'soft' or 'hard'."

    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return "Application not found or you don't have access to it."

        # Find primary borrower
        primary_ab = next(
            (ab for ab in (app.application_borrowers or []) if ab.is_primary),
            None,
        )
        if primary_ab is None or primary_ab.borrower is None:
            return "No primary borrower found for this application."

        borrower = primary_ab.borrower
        bureau = get_credit_bureau_service()

        if pull_type == "soft":
            result = bureau.soft_pull(borrower.id, borrower.keycloak_user_id)
        else:
            result = bureau.hard_pull(borrower.id, borrower.keycloak_user_id)

        now = datetime.now(UTC)
        expiry_days = 30 if pull_type == "soft" else 120

        # Serialize trade lines for hard pulls
        trade_lines_json = None
        if pull_type == "hard":
            trade_lines_json = [tl.model_dump(mode="json") for tl in result.trade_lines]

        report = CreditReport(
            borrower_id=borrower.id,
            application_id=application_id,
            pull_type=pull_type,
            credit_score=result.credit_score,
            bureau=result.bureau,
            outstanding_accounts=result.outstanding_accounts,
            total_outstanding_debt=result.total_outstanding_debt,
            derogatory_marks=result.derogatory_marks,
            oldest_account_years=result.oldest_account_years,
            trade_lines=trade_lines_json,
            collections_count=getattr(result, "collections_count", None),
            bankruptcy_flag=getattr(result, "bankruptcy_flag", None),
            public_records_count=getattr(result, "public_records_count", None),
            pulled_at=now,
            pulled_by=user.user_id,
            expires_at=now + timedelta(days=expiry_days),
        )
        session.add(report)

        await write_audit_event(
            session,
            event_type="credit_pull",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "pull_type": pull_type,
                "bureau": result.bureau,
                "credit_score": result.credit_score,
                "borrower_id": borrower.id,
            },
        )
        await session.commit()

    lines = [
        f"Credit {pull_type} pull complete for {borrower.first_name} {borrower.last_name}:",
        f"Bureau: {result.bureau}",
        f"Credit score: {result.credit_score}",
        f"Outstanding accounts: {result.outstanding_accounts}",
        f"Total outstanding debt: ${result.total_outstanding_debt:,.2f}",
        f"Derogatory marks: {result.derogatory_marks}",
        f"Oldest account: {result.oldest_account_years} years",
        f"Expires: {report.expires_at.strftime('%Y-%m-%d')}",
    ]

    if pull_type == "hard":
        lines.append(f"Trade lines: {len(result.trade_lines)}")
        lines.append(f"Collections: {result.collections_count}")
        lines.append(f"Bankruptcy flag: {result.bankruptcy_flag}")
        lines.append(f"Public records: {result.public_records_count}")

    return "\n".join(lines)


@tool
async def lo_prequalification_check(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Run a pre-qualification evaluation for a loan application.

    Uses the bureau credit score from the most recent soft pull (not the
    self-reported score). Requires a credit pull to be on file first.

    Args:
        application_id: The loan application ID.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return "Application not found or you don't have access to it."

        # Load most recent soft-pull credit report
        stmt = (
            select(CreditReport)
            .where(
                CreditReport.application_id == application_id,
                CreditReport.pull_type == "soft",
            )
            .order_by(CreditReport.pulled_at.desc())
            .limit(1)
        )
        cr = (await session.execute(stmt)).scalar_one_or_none()
        if cr is None:
            return (
                "No soft credit pull on file for this application. "
                "Use lo_pull_credit with pull_type='soft' first."
            )

        # Check expiration
        now = datetime.now(UTC)
        expired_warning = ""
        if cr.expires_at and cr.expires_at < now:
            expired_warning = (
                "WARNING: Credit report expired on "
                f"{cr.expires_at.strftime('%Y-%m-%d')}. Consider pulling fresh credit.\n\n"
            )

        # Load financials
        financials = await get_financials(session, application_id)
        if not financials:
            return "No financial data found for this application. Borrower needs to provide income and debt information."

        fin = financials[0]
        gross_monthly_income = fin.gross_monthly_income or Decimal("0")
        monthly_debts = fin.monthly_debts or Decimal("0")
        loan_amount = app.loan_amount or Decimal("0")
        property_value = app.property_value or Decimal("0")

        if loan_amount <= 0 or property_value <= 0:
            return "Loan amount and property value must be set on the application before running pre-qualification."

        loan_type = app.loan_type.value if app.loan_type else None

        result = evaluate_prequalification(
            credit_score=cr.credit_score,
            gross_monthly_income=gross_monthly_income,
            monthly_debts=monthly_debts,
            loan_amount=loan_amount,
            property_value=property_value,
            loan_type=loan_type,
        )

        await write_audit_event(
            session,
            event_type="prequalification_reviewed",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "credit_score_used": cr.credit_score,
                "dti_ratio": result.dti_ratio,
                "ltv_ratio": result.ltv_ratio,
                "eligible_count": len(result.eligible_products),
                "recommended": result.recommended_product_id,
            },
        )
        await session.commit()

    # Format output
    lines = [expired_warning] if expired_warning else []
    lines.extend(
        [
            f"Pre-qualification evaluation for application #{application_id}:",
            f"Bureau credit score: {cr.credit_score} (pulled {cr.pulled_at.strftime('%Y-%m-%d')})",
            f"Gross monthly income: ${gross_monthly_income:,.2f}",
            f"Monthly debts: ${monthly_debts:,.2f}",
            f"Loan amount: ${loan_amount:,.2f}",
            f"Property value: ${property_value:,.2f}",
            f"DTI: {result.dti_ratio:.1f}%  |  LTV: {result.ltv_ratio:.1f}%  |  Down payment: {result.down_payment_pct:.1f}%",
            "",
        ]
    )

    if result.eligible_products:
        lines.append(f"ELIGIBLE ({len(result.eligible_products)}):")
        for p in result.eligible_products:
            rec = " ** RECOMMENDED" if p.product_id == result.recommended_product_id else ""
            lines.append(
                f"  - {p.product_name}: max ${p.max_loan_amount:,.2f} "
                f"at {p.estimated_rate:.2f}% (${p.estimated_monthly_payment:,.2f}/mo){rec}"
            )
        lines.append("")

    if result.ineligible_products:
        lines.append(f"INELIGIBLE ({len(result.ineligible_products)}):")
        for p in result.ineligible_products:
            reasons = "; ".join(p.ineligibility_reasons)
            lines.append(f"  - {p.product_name}: {reasons}")
        lines.append("")

    lines.append(result.summary)

    return "\n".join(lines)


@tool
async def lo_issue_prequalification(
    application_id: int,
    product_id: str,
    max_amount: float,
    state: Annotated[dict, InjectedState],
    notes: str | None = None,
) -> str:
    """Issue a pre-qualification decision for an application.

    Transitions the application from INQUIRY to PREQUALIFICATION and records
    the decision. The application must be in the INQUIRY stage.

    Args:
        application_id: The loan application ID.
        product_id: The mortgage product ID (e.g., "conventional_30", "fha").
        max_amount: The maximum pre-qualified loan amount.
        notes: Optional notes from the loan officer.
    """
    if product_id not in _VALID_PRODUCT_IDS:
        valid = ", ".join(sorted(_VALID_PRODUCT_IDS))
        return f"Invalid product_id '{product_id}'. Must be one of: {valid}"

    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await get_application(session, user, application_id)
        if app is None:
            return "Application not found or you don't have access to it."

        current_stage = app.stage or ApplicationStage.INQUIRY
        if current_stage != ApplicationStage.INQUIRY:
            return (
                f"Application is in '{current_stage.value}' stage. "
                "Pre-qualification can only be issued from the INQUIRY stage."
            )

        # Load latest soft pull for credit score
        stmt = (
            select(CreditReport)
            .where(
                CreditReport.application_id == application_id,
                CreditReport.pull_type == "soft",
            )
            .order_by(CreditReport.pulled_at.desc())
            .limit(1)
        )
        cr = (await session.execute(stmt)).scalar_one_or_none()
        if cr is None:
            return "No soft credit pull on file. Pull credit before issuing pre-qualification."

        # Compute DTI (including housing payment) and LTV for the decision record
        financials = await get_financials(session, application_id)
        if not financials:
            return "No financial records on file. Borrower must submit financials before pre-qualification."
        fin = financials[0]
        gross_monthly_income = float(fin.gross_monthly_income or 0)
        monthly_debts = float(fin.monthly_debts or 0)
        loan_amount = float(app.loan_amount or 0)
        property_value = float(app.property_value or 0)

        ltv = (loan_amount / property_value) if property_value > 0 else 1.0

        # DTI must include the estimated housing payment to match the
        # evaluate_prequalification formula used for eligibility decisions.
        product_rate_for_dti = next((p.typical_rate for p in PRODUCTS if p.id == product_id), 0.0)
        term_months = 360 if "30" in product_id or "arm" in product_id else 180
        monthly_payment = compute_monthly_payment(loan_amount, product_rate_for_dti, term_months)
        total_obligations = monthly_debts + monthly_payment
        dti = total_obligations / gross_monthly_income if gross_monthly_income > 0 else 1.0

        # Find product name for the confirmation message
        product_name = next((p.name for p in PRODUCTS if p.id == product_id), product_id)
        product_rate = next((p.typical_rate for p in PRODUCTS if p.id == product_id), 0.0)

        now = datetime.now(UTC)

        # Upsert: record superseded audit event for prior decision, then replace
        existing_stmt = select(PrequalificationDecision).where(
            PrequalificationDecision.application_id == application_id
        )
        existing_row = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing_row is not None:
            await write_audit_event(
                session,
                event_type="prequalification_superseded",
                user_id=user.user_id,
                application_id=application_id,
                event_data={
                    "prior_product_id": existing_row.product_id,
                    "prior_max_loan_amount": float(existing_row.max_loan_amount),
                    "prior_issued_at": existing_row.issued_at.isoformat(),
                    "reason": "replaced_by_new_decision",
                },
            )
            await session.delete(existing_row)

        decision = PrequalificationDecision(
            application_id=application_id,
            product_id=product_id,
            max_loan_amount=Decimal(str(max_amount)),
            estimated_rate=Decimal(str(product_rate)),
            credit_score_at_decision=cr.credit_score,
            dti_at_decision=Decimal(str(round(dti, 4))),
            ltv_at_decision=Decimal(str(round(ltv, 4))),
            issued_by=user.user_id,
            issued_at=now,
            expires_at=now + timedelta(days=90),
            notes=notes,
        )
        session.add(decision)

        # Transition INQUIRY -> PREQUALIFICATION
        try:
            await transition_stage(
                session,
                user,
                application_id,
                ApplicationStage.PREQUALIFICATION,
            )
        except InvalidTransitionError as e:
            return str(e)

        await write_audit_event(
            session,
            event_type="prequalification_issued",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "product_id": product_id,
                "max_loan_amount": max_amount,
                "credit_score": cr.credit_score,
                "dti": round(dti, 4),
                "ltv": round(ltv, 4),
            },
        )
        await session.commit()

    return (
        f"Pre-qualification issued for application #{application_id}:\n"
        f"Product: {product_name}\n"
        f"Max amount: ${max_amount:,.2f}\n"
        f"Rate: {product_rate:.2f}%\n"
        f"Expires: {decision.expires_at.strftime('%Y-%m-%d')}\n"
        f"Stage transitioned to: PREQUALIFICATION"
    )
