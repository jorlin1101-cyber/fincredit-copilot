# This project was developed with assistance from AI tools.
"""LangGraph tools for the borrower assistant agent.

These wrap the completeness and status services so the agent can
check document requirements, application status, and regulatory
deadlines during a conversation.  DB-backed tools use InjectedState
to receive the caller's identity from the graph state.

Design note -- session-per-tool-call:
    Each tool opens its own ``SessionLocal()`` context rather than sharing
    a single session across the agent turn.  This is intentional: LangGraph
    tool nodes run as independent async tasks and may execute in any order,
    so sharing a session would risk interleaved flushes, stale reads, and
    MissingGreenlet errors.  The per-tool pattern keeps each DB interaction
    self-contained and avoids cross-tool state leakage.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from db.database import SessionLocal
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from ..services import application as app_service
from ..services.audit import write_audit_event
from ..services.completeness import DOC_TYPE_LABELS, check_completeness
from ..services.condition import (
    check_condition_documents,
    get_conditions,
    respond_to_condition,
)
from ..services.disclosure import (
    DISCLOSURE_BY_ID,
    get_disclosure_status,
    record_disclosure_acknowledgment,
)
from ..services.document import list_documents
from ..services.intake import (
    get_application_progress,
    update_application_fields,
)
from ..services.intake import (
    start_application as start_application_service,
)
from ..services.rate_lock import get_rate_lock_status
from ..services.status import get_application_status
from .shared import format_enum_label, user_context_from_state

_REGULATORY_DISCLAIMER = (
    "\n\n*本提示仅用于虚构项目演示，不构成法律、监管或授信意见。"
    "实际办理时限以受理机构公示、合同约定和申请当日有效政策为准。*"
)

_QUALITY_FLAG_LABELS = {
    "blurry": "图像模糊",
    "low_resolution": "分辨率较低",
    "cut_off": "内容被截断",
    "glare": "存在反光",
    "unsigned": "缺少签字",
    "expired": "材料已过期",
    "missing_pages": "页面不完整",
}

_EXTRACTION_FIELD_LABELS = {
    "employer_name": "工作单位",
    "annual_income": "年收入",
    "gross_pay": "应发工资",
    "pay_period": "工资周期",
    "ytd_earnings": "本年累计收入",
    "institution": "金融机构",
    "account_type": "账户类型",
    "ending_balance": "期末余额",
    "statement_period": "账单期间",
    "full_name": "姓名",
    "issuing_authority": "签发机关",
    "expiry_date": "有效期至",
}

_FIELD_LABELS = {
    "first_name": "名",
    "last_name": "姓",
    "email": "电子邮箱",
    "id_number": "居民身份证号码",
    "ssn": "居民身份证号码",
    "date_of_birth": "出生日期",
    "employment_status": "就业状态",
    "loan_type": "贷款类型",
    "property_address": "房产地址",
    "loan_amount": "贷款金额",
    "property_value": "房产价值",
    "gross_monthly_income": "家庭月收入",
    "monthly_debts": "每月负债",
    "total_assets": "资产合计",
    "credit_score": "模拟征信评分",
}


def _field_label(value: str) -> str:
    return _FIELD_LABELS.get(value, value)


def _user_context_from_state(state: dict):
    return user_context_from_state(state, default_role="borrower")


@tool
async def list_my_applications(
    state: Annotated[dict, InjectedState],
) -> str:
    """List the borrower's mortgage applications. Use this to discover the borrower's application IDs before calling other tools that require an application_id."""
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        apps, total = await app_service.list_applications(session, user, limit=10)

    if total == 0:
        return "您目前还没有住房贷款申请。需要我引导您开始填写吗？"

    lines = [f"您共有 {total} 笔住房贷款申请："]
    for app in apps:
        stage = format_enum_label(app.stage.value)
        loan_amt = f"¥{app.loan_amount:,.0f}" if app.loan_amount else "金额待补充"
        addr = app.property_address or "房产地址待补充"
        lines.append(f"  申请 #{app.id}：{stage}，贷款金额 {loan_amt}，{addr}")

    if total == 1:
        lines.append(f"\n当前申请编号为 {apps[0].id}。")

    return "\n".join(lines)


@tool
async def document_completeness(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Check which documents have been uploaded and which are still needed for a loan application.

    Args:
        application_id: The loan application ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await check_completeness(session, user, application_id)

    if result is None:
        return "未找到该申请，或您没有查看权限。"

    lines = [
        f"申请 #{application_id} 的材料完整度：",
        f"状态：{'材料齐全' if result.is_complete else '仍需补充'}"
        f"（已提供 {result.provided_count}/{result.required_count} 项）",
        "",
    ]
    for req in result.requirements:
        status = "已提供" if req.is_provided else "未提供"
        line = f"- {req.label}: {status}"
        if req.quality_flags:
            issues = [_QUALITY_FLAG_LABELS.get(flag, flag) for flag in req.quality_flags]
            line += f"（需关注：{'、'.join(issues)}）"
        lines.append(line)

    missing = [r for r in result.requirements if not r.is_provided]
    if missing:
        lines.append("")
        lines.append("下一步：请上传" + missing[0].label)

    return "\n".join(lines)


_STATUS_LABELS: dict[str, str] = {
    "uploaded": "已上传，等待处理",
    "processing": "识别处理中",
    "processing_complete": "识别完成",
    "processing_failed": "识别失败",
    "pending_review": "待复核",
    "accepted": "已通过",
    "flagged_for_resubmission": "需重新上传",
    "rejected": "未通过",
}


@tool
async def document_processing_status(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Check the processing status of documents uploaded for a loan application. Shows each document's current status (processing, complete, failed, etc.).

    Args:
        application_id: The loan application ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        documents, total = await list_documents(session, user, application_id, limit=50)

    if total == 0:
        return (
            f"申请 #{application_id} 尚未上传材料。需要我说明应准备哪些材料吗？"
        )

    lines = [f"申请 #{application_id} 的材料处理状态（共 {total} 项）："]

    processing_count = 0
    failed_count = 0
    complete_count = 0

    for doc in documents:
        status_val = doc.status.value if hasattr(doc.status, "value") else str(doc.status)
        label = DOC_TYPE_LABELS.get(doc.doc_type, str(doc.doc_type))
        status_label = _STATUS_LABELS.get(status_val, status_val)
        lines.append(f"- {label}: {status_label}")

        if status_val == "processing":
            processing_count += 1
        elif status_val == "processing_failed":
            failed_count += 1
        elif status_val == "processing_complete":
            complete_count += 1

    if processing_count > 0:
        lines.append("")
        lines.append(f"仍有 {processing_count} 项材料正在识别，请稍后刷新查看。")
    if failed_count > 0:
        lines.append("")
        lines.append(f"有 {failed_count} 项材料识别失败，请重新上传清晰、完整的文件。")

    return "\n".join(lines)


@tool
async def application_status(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Get the current status summary for a loan application including stage, document progress, and pending actions.

    Args:
        application_id: The loan application ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await get_application_status(session, user, application_id)

    if result is None:
        return "未找到该申请，或您没有查看权限。"

    lines = [
        f"申请 #{application_id} 当前状态：",
        f"阶段：{result.stage_info.label}",
        f"  {result.stage_info.description}",
        f"  下一步：{result.stage_info.next_step}",
        f"  参考时长：{result.stage_info.typical_timeline}",
        "",
        f"申请材料：{result.provided_doc_count}/{result.required_doc_count} 项"
        f"（{'齐全' if result.is_document_complete else '仍需补充'}）",
    ]

    if result.open_condition_count > 0:
        lines.append(f"待处理审批条件：{result.open_condition_count} 项")

    if result.pending_actions:
        lines.append("")
        lines.append("待办事项：")
        for action in result.pending_actions:
            lines.append(f"- {action.description}")

    return "\n".join(lines)


@tool
def regulatory_deadlines(
    application_date: str,
    current_stage: str,
) -> str:
    """显示申请进度时长和需向受理机构确认的办理节点。

    Args:
        application_date: The date the application was created (YYYY-MM-DD format).
        current_stage: The current application stage (e.g. 'application', 'processing').
    """
    try:
        app_date = datetime.strptime(application_date, "%Y-%m-%d").date()
    except ValueError:
        return "日期格式无效，请使用 YYYY-MM-DD。" + _REGULATORY_DISCLAIMER

    today = date.today()
    elapsed = max((today - app_date).days, 0)
    lines = [f"申请日期：{application_date}，已进入流程 {elapsed} 天。"]

    # Pre-application stages don't trigger regulatory clocks
    pre_app_stages = {"inquiry", "prequalification"}
    if current_stage in pre_app_stages:
        lines.append("当前仍处于咨询或预审阶段，正式办理时限通常从受理完整申请后开始计算。")
        return "\n".join(lines) + _REGULATORY_DISCLAIMER

    lines.extend(
        [
            "- 请确认受理机构是否已登记为完整申请，以及当前缺少的材料。",
            "- 请核对机构公示或合同约定的审批、面签、抵押登记和放款时限。",
            "- 如进度长时间未更新，请联系客户经理查询具体原因。",
        ]
    )

    return "\n".join(lines) + _REGULATORY_DISCLAIMER


@tool
async def acknowledge_disclosure(
    application_id: int,
    disclosure_id: str,
    borrower_confirmation: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Record a borrower's acknowledgment of a required disclosure in the audit trail.

    Call this when the borrower confirms they have received and reviewed
    a disclosure (e.g., "yes", "I acknowledge", "I agree").

    Args:
        application_id: The loan application ID.
        disclosure_id: Identifier of the disclosure (loan_estimate, privacy_notice, hmda_notice, equal_opportunity_notice).
        borrower_confirmation: The borrower's exact confirmation text.
    """
    disclosure = DISCLOSURE_BY_ID.get(disclosure_id)
    if disclosure is None:
        valid = ", ".join(sorted(DISCLOSURE_BY_ID.keys()))
        return f"未识别的告知文件“{disclosure_id}”。可用标识：{valid}。"

    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        await record_disclosure_acknowledgment(
            session,
            user,
            application_id,
            disclosure_id,
            borrower_confirmation,
        )

    return f"已记录：申请 #{application_id} 的《{disclosure['label']}》已查看并确认。"


@tool
async def disclosure_status(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Check which required disclosures have been acknowledged and which are still pending for a loan application.

    Args:
        application_id: The loan application ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        # Verify user has access to this application
        app = await app_service.get_application(session, user, application_id)
        if app is None:
            return f"未找到申请 #{application_id}，或您没有查看权限。"
        result = await get_disclosure_status(session, application_id)

    lines = [f"申请 #{application_id} 的信息披露确认状态："]

    if result["all_acknowledged"]:
        lines.append("全部必需告知文件均已查看并确认。")
    else:
        lines.append(
            f"{len(result['acknowledged'])}/{len(result['acknowledged']) + len(result['pending'])} "
            " 项已确认。"
        )

    if result["acknowledged"]:
        lines.append("")
        lines.append("已确认：")
        for d_id in result["acknowledged"]:
            label = DISCLOSURE_BY_ID.get(d_id, {}).get("label", d_id)
            lines.append(f"  - {label}")

    if result["pending"]:
        lines.append("")
        lines.append("待确认：")
        for d_id in result["pending"]:
            label = DISCLOSURE_BY_ID.get(d_id, {}).get("label", d_id)
            lines.append(f"  - {label}")

    return "\n".join(lines)


@tool
async def rate_lock_status(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Check the current rate lock status for a loan application, including locked rate, expiration date, and days remaining.

    Args:
        application_id: The loan application ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await get_rate_lock_status(session, user, application_id)

    if result is None:
        return "未找到该申请，或您没有查看权限。"

    if result["status"] == "none":
        return (
            f"申请 #{application_id} 当前没有已锁定的执行利率。需要我说明利率锁定的含义吗？"
        )

    lines = [f"申请 #{application_id} 的利率锁定状态："]

    if result["status"] == "active":
        lines.append("状态：有效")
        lines.append(f"锁定利率：{result['locked_rate']}%")
        lines.append(f"锁定日期：{result['lock_date']}")
        lines.append(f"有效期至：{result['expiration_date']}")
        days = result["days_remaining"]
        lines.append(f"剩余：{days} 天")

        if days == 0:
            lines.append("")
            lines.append("利率锁定今日到期，请尽快联系客户经理确认后续安排。")
        elif days <= 3:
            lines.append("")
            lines.append(f"提示：利率锁定将在 {days} 天后到期，请尽快联系客户经理。")
        elif days <= 7:
            lines.append("")
            lines.append(f"提示：利率锁定将在 {days} 天后到期，请关注签约与放款进度。")
    else:
        lines.append("状态：已到期")
        lines.append(f"原锁定利率：{result['locked_rate']}%")
        lines.append(f"到期日期：{result['expiration_date']}")
        lines.append("")
        lines.append("原利率锁定已到期，请联系客户经理按当前政策和产品重新确认执行利率。")

    return "\n".join(lines)


@tool
async def list_conditions(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """List underwriting conditions for a loan application. Shows open and responded conditions that the borrower needs to address.

    Args:
        application_id: The loan application ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await get_conditions(session, user, application_id, open_only=True)

    if result is None:
        return "未找到该申请，或您没有查看权限。"

    if not result:
        return f"申请 #{application_id} 当前没有待处理的审批条件。"

    lines = [f"申请 #{application_id} 的待处理审批条件："]
    for i, cond in enumerate(result, 1):
        status_label = format_enum_label(cond["status"])
        line = f"{i}. [{status_label}] {cond['description']}（条件 #{cond['id']}）"
        if cond.get("response_text"):
            line += f"\n   您的回复：{cond['response_text']}"
        lines.append(line)

    open_count = sum(1 for c in result if c["status"] == "open")
    if open_count > 0:
        lines.append("")
        lines.append(f"您还有 {open_count} 项条件需要处理。现在开始处理吗？")

    return "\n".join(lines)


@tool
async def respond_to_condition_tool(
    application_id: int,
    condition_id: int,
    response_text: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Record the borrower's text response to an underwriting condition. Use this when the borrower provides an explanation or answer for a condition.

    Args:
        application_id: The loan application ID.
        condition_id: The condition ID to respond to (from list_conditions output).
        response_text: The borrower's response text.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await respond_to_condition(
            session,
            user,
            application_id,
            condition_id,
            response_text,
        )

    if result is None:
        return "未找到该申请或审批条件，或您没有操作权限。"

    return (
        f"已记录您对条件 #{result['id']}“{result['description']}”的回复。"
        "审批人员将进行复核。"
    )


@tool
async def check_condition_satisfaction(
    application_id: int,
    condition_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Check whether a condition has been satisfied by reviewing linked documents and their extraction results. Use this after a borrower uploads a document for a condition.

    Args:
        application_id: The loan application ID.
        condition_id: The condition ID to check.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await check_condition_documents(
            session,
            user,
            application_id,
            condition_id,
        )

    if result is None:
        return "未找到该申请或审批条件，或您没有查看权限。"

    lines = [f"审批条件 #{result['condition_id']}：{result['description']}"]
    lines.append(f"状态：{format_enum_label(result['status'])}")

    if result["response_text"]:
        lines.append(f"借款人回复：{result['response_text']}")

    if not result["has_documents"]:
        lines.append("")
        lines.append("该条件尚未关联材料。")
        if result["response_text"]:
            lines.append("借款人已提交文字说明，需人工判断是否充分或仍需补充材料。")
        return "\n".join(lines)

    lines.append("")
    lines.append(f"关联材料（{len(result['documents'])} 项）：")
    for doc in result["documents"]:
        label = doc["file_path"].rsplit("/", 1)[-1] if doc.get("file_path") else f"doc-{doc['id']}"
        doc_line = (
            f"  - {label}（类型：{format_enum_label(doc['doc_type'])}，"
            f"状态：{format_enum_label(doc['status'])}）"
        )
        lines.append(doc_line)

        if doc["quality_flags"]:
            issues = [_QUALITY_FLAG_LABELS.get(flag, flag) for flag in doc["quality_flags"]]
            lines.append(f"    质量提示：{'、'.join(issues)}")

        if doc["extractions"]:
            lines.append("    识别字段：")
            for ext in doc["extractions"]:
                conf = f"（置信度：{ext['confidence']:.0%}）" if ext["confidence"] else ""
                field_label = _EXTRACTION_FIELD_LABELS.get(ext["field"], ext["field"])
                lines.append(f"      {field_label}：{ext['value']}{conf}")

    if result["has_quality_issues"]:
        lines.append("")
        lines.append("上传材料存在质量问题，建议请借款人重新上传清晰、完整的版本。")
    else:
        lines.append("")
        lines.append("材料当前未发现明显质量问题，仍须由审批人员核验内容真实性和条件满足情况。")

    return "\n".join(lines)


@tool
async def start_application(
    state: Annotated[dict, InjectedState],
) -> str:
    """Start a new mortgage application or continue an existing one.

    Call this when the borrower expresses intent to apply for a mortgage.
    If they already have an active application, it returns that instead
    of creating a duplicate.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        result = await start_application_service(session, user)

        if result["is_new"]:
            await write_audit_event(
                session,
                event_type="application_started",
                user_id=user.user_id,
                user_role=user.role.value,
                application_id=result["application_id"],
                event_data={"source": "conversational_intake"},
            )
            await session.commit()
            return (
                f"已创建申请 #{result['application_id']}。接下来我会引导您填写个人资料、"
                "房产信息和财务情况。"
            )

        stage = format_enum_label(result["stage"])
        return (
            f"您已有一笔进行中的申请 #{result['application_id']}（阶段：{stage}）。"
            "是否继续完善这笔申请？"
        )


@tool
async def update_application_data(
    application_id: int,
    fields: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Update one or more fields on a mortgage application.

    Args:
        application_id: The application ID to update.
        fields: JSON string of field_name:value pairs, e.g.
            '{"gross_monthly_income": "6250", "employment_status": "w2"}'

    Valid field names: first_name, last_name, email, id_number, date_of_birth,
        employment_status, loan_type, property_address, loan_amount,
        property_value, gross_monthly_income, monthly_debts, total_assets,
        credit_score
    """
    import json as _json

    user = _user_context_from_state(state)

    try:
        parsed = _json.loads(fields)
    except _json.JSONDecodeError:
        return "无法解析填写内容，请提交有效的数据格式。"

    if not isinstance(parsed, dict) or not parsed:
        return "填写内容不能为空。"

    async with SessionLocal() as session:
        result = await update_application_fields(session, user, application_id, parsed)

        # Write audit event (field names only, not PII values)
        audit_data = {
            "fields_updated": result["updated"],
            "fields_failed": list(result["errors"].keys()),
        }
        if result.get("corrections"):
            audit_data["corrections"] = list(result["corrections"].keys())

        await write_audit_event(
            session,
            event_type="data_collection",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data=audit_data,
        )
        await session.commit()

    # Format response
    parts = []
    if result["updated"]:
        parts.append(f"已更新：{'、'.join(_field_label(item) for item in result['updated'])}。")
    if result["errors"]:
        for fname, msg in result["errors"].items():
            if fname == "_":
                parts.append(msg)
            else:
                parts.append(f"{_field_label(fname)}保存失败：{msg}。")
    if result["remaining"]:
        parts.append(f"仍需补充：{'、'.join(_field_label(item) for item in result['remaining'])}。")
    else:
        parts.append("必填信息已填写完整。")

    return " ".join(parts)


@tool
async def get_application_summary(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Show collected application data and remaining fields. Use when the borrower asks to review their application, see what's been collected, or check progress.

    Args:
        application_id: The application ID to summarize.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        progress = await get_application_progress(session, user, application_id)

        if progress is None:
            return "未找到该申请，或您没有查看权限。"

        await write_audit_event(
            session,
            event_type="data_access",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={"action": "review", "tool": "get_application_summary"},
        )
        await session.commit()

    pct = round(progress["completed"] / progress["total"] * 100) if progress["total"] else 0
    stage = format_enum_label(progress["stage"])

    lines = [
        f"申请 #{progress['application_id']}（阶段：{stage}）",
        f"填写进度：{progress['completed']}/{progress['total']} 项（{pct}%）",
        "",
    ]

    for section_name, fields in progress["sections"].items():
        lines.append(f"{section_name}：")
        for label, value in fields.items():
            display = value if value is not None else "（未提供）"
            lines.append(f"  {label}：{display}")
        lines.append("")

    if progress["remaining"]:
        lines.append(f"仍需补充：{'、'.join(_field_label(item) for item in progress['remaining'])}")
    else:
        lines.append("必填信息已填写完整。")

    return "\n".join(lines)


@tool
async def prequalification_estimate(
    application_id: int,
    state: Annotated[dict, InjectedState],
) -> str:
    """Show a preliminary pre-qualification estimate based on the borrower's self-reported information.

    Uses the borrower's credit score, income, debts, loan amount, and property
    value to estimate product eligibility. Results are preliminary -- the loan
    officer will conduct a credit check for official pre-qualification.

    Args:
        application_id: The loan application ID to evaluate.
    """
    from ..services.prequalification import evaluate_prequalification

    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        app = await app_service.get_application(session, user, application_id)
        if app is None:
            return "未找到该申请，或您没有查看权限。"

        financials = await app_service.get_financials(session, application_id)

    if not financials:
        return (
            "需要先补充财务信息才能进行预审测算，包括征信评分、家庭月收入、"
            "每月负债、申请贷款金额和房产价值。"
        )

    fin = financials[0]
    missing: list[str] = []
    if not fin.credit_score:
        missing.append("征信评分")
    if not fin.gross_monthly_income:
        missing.append("家庭月收入")
    if fin.monthly_debts is None:
        missing.append("每月负债")
    if not app.loan_amount:
        missing.append("贷款金额")
    if not app.property_value:
        missing.append("房产价值")

    if missing:
        return (
            f"进行测算前还需补充：{'、'.join(missing)}。现在继续填写吗？"
        )

    loan_type = app.loan_type.value if app.loan_type else None
    result = evaluate_prequalification(
        credit_score=fin.credit_score,
        gross_monthly_income=Decimal(str(fin.gross_monthly_income)),
        monthly_debts=Decimal(str(fin.monthly_debts)),
        loan_amount=Decimal(str(app.loan_amount)),
        property_value=Decimal(str(app.property_value)),
        loan_type=loan_type,
    )

    lines = ["住房贷款预审测算", ""]
    lines.append(
        "重要提示：本结果依据您提供的信息和内部演示规则测算，不构成授信承诺。"
        "客户经理和有权审批人员仍需核验材料、征信及适用政策。"
    )
    lines.append("")
    lines.append(f"债务收入比：{result.dti_ratio:.1f}%")
    lines.append(f"贷款成数：{result.ltv_ratio:.1f}%")
    lines.append(f"首付款比例：{result.down_payment_pct:.1f}%")
    lines.append("")

    if result.eligible_products:
        lines.append(f"初步匹配产品（{len(result.eligible_products)} 个）：")
        for p in result.eligible_products:
            rec = "（参考方案）" if p.product_id == result.recommended_product_id else ""
            lines.append(
                f"  - {p.product_name}{rec}：最高参考贷款额 ¥{p.max_loan_amount:,.0f}，"
                f"测算利率 {p.estimated_rate:.3f}%，预计月供 ¥{p.estimated_monthly_payment:,.0f}"
            )
    else:
        lines.append("当前信息暂未匹配到演示产品。")

    if result.ineligible_products:
        lines.append("")
        lines.append("未匹配产品：")
        for p in result.ineligible_products:
            reasons = "；".join(p.ineligibility_reasons)
            lines.append(f"  - {p.product_name}：{reasons}")

    lines.append("")
    lines.append(result.summary)

    async with SessionLocal() as session:
        await write_audit_event(
            session,
            event_type="prequalification_estimate_viewed",
            user_id=user.user_id,
            user_role=user.role.value,
            application_id=application_id,
            event_data={
                "eligible_count": len(result.eligible_products),
                "recommended": result.recommended_product_id,
            },
        )
        await session.commit()

    return "\n".join(lines)
