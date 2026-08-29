# This project was developed with assistance from AI tools.
"""LangGraph tools for the CEO executive assistant agent.

These wrap the Analytics and Audit services so the CEO agent can answer
pipeline, performance, denial, and audit questions conversationally.

Design note -- session-per-tool-call:
    Each tool opens its own ``SessionLocal()`` context rather than sharing
    a single session across the agent turn.  See loan_officer_tools.py for
    the rationale.
"""

from datetime import datetime
from typing import Annotated

from db import Application, ApplicationBorrower, Borrower
from db.database import SessionLocal
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..services.analytics import get_denial_trends, get_lo_performance, get_pipeline_summary
from ..services.audit import (
    get_decision_trace,
    get_events_by_application,
    search_events,
    write_audit_event,
)
from ..services.model_monitoring import get_model_monitoring_summary
from .shared import format_enum_label, user_context_from_state

_LOAN_TYPE_LABELS = {
    "conventional_30": "30年期商业性个人住房贷款",
    "conventional_15": "15年期商业性个人住房贷款",
    "fha": "住房公积金个人住房贷款",
    "va": "商业贷款与公积金组合贷款",
    "jumbo": "大额商业性个人住房贷款",
    "usda": "县域住房贷款（演示产品）",
    "arm": "LPR浮动利率个人住房贷款",
}

_AUDIT_EVENT_LABELS = {
    "application_created": "申请创建",
    "application_updated": "申请更新",
    "stage_transition": "阶段变更",
    "document_uploaded": "材料上传",
    "document_processed": "材料识别完成",
    "document_status_changed": "材料状态变更",
    "condition_created": "审批条件新增",
    "condition_status_changed": "审批条件状态变更",
    "compliance_check": "合规检查",
    "decision_proposed": "授信决定待确认",
    "decision_rendered": "授信决定已记录",
    "adverse_action_notice": "授信决定告知书生成",
    "le_generated": "贷款要素确认书生成",
    "cd_generated": "签约要素确认书生成",
    "agent_tool_called": "智能助手业务操作",
    "query": "数据查询",
    "data_access": "业务数据访问",
}

_RECOMMENDATION_LABELS = {
    "approve": "可提交人工决策",
    "approve with conditions": "需重点人工复核",
    "deny": "需重点人工复核",
    "suspend": "需补充材料",
}


def _audit_event_label(value: str) -> str:
    return _AUDIT_EVENT_LABELS.get(str(value or "").strip().lower(), "其他业务操作")


def _recommendation_label(value: str) -> str:
    text = str(value or "").strip()
    return _RECOMMENDATION_LABELS.get(text.lower(), text)


def _format_timestamp(value) -> str:
    if isinstance(value, datetime):
        return value.astimezone().strftime("%Y年%m月%d日 %H:%M:%S")
    text = str(value or "")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone().strftime(
            "%Y年%m月%d日 %H:%M:%S"
        )
    except ValueError:
        return text[:19] or "时间待补充"


def _person_name(first_name: str, last_name: str) -> str:
    if any("\u4e00" <= char <= "\u9fff" for char in f"{first_name}{last_name}"):
        return f"{last_name}{first_name}"
    return f"{first_name} {last_name}"


def _user_context_from_state(state: dict):
    return user_context_from_state(state, default_role="ceo")


# ---------------------------------------------------------------------------
# Pipeline & performance tools (S-5-F13-06)
# ---------------------------------------------------------------------------


@tool
async def ceo_pipeline_summary(
    days: int = 90,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get pipeline summary: application counts by stage, pull-through rate, average days to close, and turn times.

    Args:
        days: Time range in days for historical metrics (default 90).
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        summary = await get_pipeline_summary(session, days=days)
        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={"tool": "ceo_pipeline_summary", "days": days},
        )
        await session.commit()

    lines = [
        f"业务管线概览（近 {summary.time_range_days} 天）：",
        f"当前申请总数：{summary.total_applications}",
        "",
        "按阶段：",
    ]
    for sc in summary.by_stage:
        lines.append(f"  {format_enum_label(sc.stage)}：{sc.count}")

    lines.append("")
    lines.append(f"申请转化率：{summary.pull_through_rate}%")
    if summary.avg_days_to_close is not None:
        lines.append(f"平均结案时长：{summary.avg_days_to_close} 天")

    if summary.turn_times:
        lines.append("")
        lines.append("阶段流转时长：")
        for tt in summary.turn_times:
            from_label = format_enum_label(tt.from_stage)
            to_label = format_enum_label(tt.to_stage)
            lines.append(f"  {from_label} → {to_label}：{tt.avg_days} 天（样本 {tt.sample_size} 笔）")

    return "\n".join(lines)


@tool
async def ceo_denial_trends(
    days: int = 90,
    product: str | None = None,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get denial rate trends: overall rate, time-based trend, top reasons, and per-product breakdown.

    Args:
        days: Time range in days (default 90).
        product: Optional loan type filter (e.g. 'conventional_30', 'fha', 'va').
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        try:
            trends = await get_denial_trends(session, days=days, product=product)
        except ValueError:
            return "产品筛选条件无效，请选择页面提供的住房贷款产品。"

        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={"tool": "ceo_denial_trends", "days": days, "product": product},
        )
        await session.commit()

    lines = [
        f"未通过趋势（近 {trends.time_range_days} 天）：",
        f"总体未通过率：{trends.overall_denial_rate}%",
        f"决策总数：{trends.total_decisions}，未通过：{trends.total_denials}",
    ]

    if trends.trend:
        lines.append("")
        lines.append("变化趋势：")
        for pt in trends.trend:
            lines.append(
                f"  {pt.period}：{pt.denial_rate}%（{pt.denial_count}/{pt.total_decided}）"
            )

    if trends.top_reasons:
        lines.append("")
        lines.append("主要未通过原因：")
        for r in trends.top_reasons:
            lines.append(f"  {r.reason}：{r.count}（{r.percentage}%）")

    if trends.by_product:
        lines.append("")
        lines.append("按产品：")
        for prod, rate in trends.by_product.items():
            lines.append(f"  {_LOAN_TYPE_LABELS.get(prod, prod)}：{rate}%")

    return "\n".join(lines)


@tool
async def ceo_lo_performance(
    days: int = 90,
    product: str | None = None,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get loan officer performance metrics: active pipeline, closed count, pull-through, turn times, denial rate.

    Args:
        days: Time range in days (default 90).
        product: Optional loan type filter (e.g. 'conventional_30', 'fha').
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        try:
            summary = await get_lo_performance(session, days=days, product=product)
        except ValueError:
            return "产品筛选条件无效，请选择页面提供的住房贷款产品。"

        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={"tool": "ceo_lo_performance", "days": days, "product": product},
        )
        await session.commit()

    if not summary.loan_officers:
        return "所选时间范围内暂无客户经理绩效数据。"

    lines = [f"客户经理绩效（近 {summary.time_range_days} 天）：", ""]
    for lo in summary.loan_officers:
        name = lo.lo_name or lo.lo_id
        lines.append(f"{name}：")
        lines.append(f"  在途申请：{lo.active_count}")
        lines.append(f"  已结案：{lo.closed_count}")
        lines.append(f"  申请转化率：{lo.pull_through_rate}%")
        lines.append(f"  未通过率：{lo.denial_rate}%")
        if lo.avg_days_to_underwriting is not None:
            lines.append(f"  进入授信审批平均时长：{lo.avg_days_to_underwriting} 天")
        if lo.avg_days_conditions_to_cleared is not None:
            lines.append(f"  审批条件处理平均时长：{lo.avg_days_conditions_to_cleared} 天")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Application & audit lookup tools (S-5-F13-08)
# ---------------------------------------------------------------------------


@tool
async def ceo_application_lookup(
    borrower_name: str | None = None,
    application_id: int | None = None,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Look up a loan application by borrower name or application ID.

    Returns current stage, assigned LO, loan details, and outstanding conditions.
    PII fields are masked by the middleware for CEO role.

    Args:
        borrower_name: Borrower's name to search for (partial match).
        application_id: Specific application ID to look up.
    """
    if not borrower_name and not application_id:
        return "请提供借款人姓名或申请编号。"

    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        eager = selectinload(Application.application_borrowers).joinedload(
            ApplicationBorrower.borrower
        )
        if application_id:
            stmt = select(Application).options(eager).where(Application.id == application_id)
        else:
            stmt = (
                select(Application)
                .options(eager)
                .join(ApplicationBorrower)
                .join(Borrower)
                .where((Borrower.first_name + " " + Borrower.last_name).ilike(f"%{borrower_name}%"))
            )

        result = await session.execute(stmt)
        apps = result.scalars().unique().all()

        if not apps:
            await write_audit_event(
                session,
                event_type="query",
                user_id=user.user_id,
                user_role=user.role.value,
                event_data={
                    "tool": "ceo_application_lookup",
                    "borrower_name": borrower_name,
                    "application_id": application_id,
                    "result": "not_found",
                },
            )
            await session.commit()
            if borrower_name:
                return (
                    f"未找到与“{borrower_name}”匹配的申请，请尝试使用申请编号查询。"
                )
            return f"未找到申请 #{application_id}。"

        # Format inside session to avoid DetachedInstanceError
        lines = []
        for app in apps:
            stage = app.stage.value if app.stage else "inquiry"
            lines.append(f"申请 #{app.id}：")
            lines.append(f"  办理阶段：{format_enum_label(stage)}")
            if app.assigned_to:
                lines.append(f"  客户经理：{app.assigned_to}")
            if app.loan_type:
                lines.append(
                    f"  贷款类型：{_LOAN_TYPE_LABELS.get(app.loan_type.value, app.loan_type.value)}"
                )
            if app.loan_amount:
                lines.append(f"  贷款金额：¥{app.loan_amount:,.2f}")
            if app.property_address:
                lines.append(f"  房产地址：{app.property_address}")

            for ab in app.application_borrowers or []:
                if ab.borrower:
                    b = ab.borrower
                    role_label = "主借款人" if ab.is_primary else "共同借款人"
                    lines.append(f"  {role_label}：{_person_name(b.first_name, b.last_name)}")

            lines.append("")

        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={
                "tool": "ceo_application_lookup",
                "borrower_name": borrower_name,
                "application_id": application_id,
            },
        )
        await session.commit()

    return "\n".join(lines)


@tool
async def ceo_audit_trail(
    application_id: int,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get the audit trail for a specific application, showing all events in chronological order.

    Args:
        application_id: The application ID to get audit events for.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        events = await get_events_by_application(session, application_id)

        if not events:
            await write_audit_event(
                session,
                event_type="query",
                user_id=user.user_id,
                user_role=user.role.value,
                event_data={"tool": "ceo_audit_trail", "application_id": application_id},
            )
            await session.commit()
            return f"申请 #{application_id} 暂无审计事件。"

        # Format inside session to avoid DetachedInstanceError
        lines = [f"申请 #{application_id} 的审计记录（{len(events)} 条）：", ""]
        for evt in events:
            ts = _format_timestamp(evt.timestamp)
            line = f"  [{ts}] {_audit_event_label(evt.event_type)}"
            if evt.user_id:
                line += f"（操作人：{evt.user_id}）"
            lines.append(line)

        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={"tool": "ceo_audit_trail", "application_id": application_id},
        )
        await session.commit()

    return "\n".join(lines)


@tool
async def ceo_decision_trace(
    decision_id: int,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get a backward trace from a specific underwriting decision to all contributing events.

    Shows decision metadata, rationale, AI recommendation, and all audit events
    that led to the decision, grouped by type.

    Args:
        decision_id: The decision ID to trace.
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        trace = await get_decision_trace(session, decision_id)

        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={"tool": "ceo_decision_trace", "decision_id": decision_id},
        )
        await session.commit()

    if trace is None:
        return f"未找到决策 #{decision_id}。"

    lines = [
        f"决策 #{trace['decision_id']} 的追溯记录：",
        f"  申请：#{trace['application_id']}",
    ]
    if trace.get("decision_type"):
        lines.append(f"  类型：{format_enum_label(trace['decision_type'])}")
    if trace.get("decided_by"):
        lines.append(f"  决策人：{trace['decided_by']}")
    if trace.get("rationale"):
        lines.append(f"  决策依据：{trace['rationale']}")
    if trace.get("ai_recommendation"):
        lines.append(f"  系统辅助建议：{_recommendation_label(trace['ai_recommendation'])}")
    if trace.get("ai_agreement") is not None:
        lines.append(f"  与系统建议一致：{'是' if trace['ai_agreement'] else '否'}")
    if trace.get("override_rationale"):
        lines.append(f"  人工调整理由：{trace['override_rationale']}")

    events_by_type = trace.get("events_by_type", {})
    if events_by_type:
        lines.append("")
        lines.append(f"关联事件（共 {trace.get('total_events', 0)} 条）：")
        for event_type, events in events_by_type.items():
            lines.append(f"  {_audit_event_label(event_type)}：{len(events)} 条")

    return "\n".join(lines)


@tool
async def ceo_audit_search(
    days: int | None = None,
    event_type: str | None = None,
    limit: int = 100,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Search audit events by time range and/or event type.

    Args:
        days: Time range in days (e.g. 7 for last week, 30 for last month).
        event_type: Filter by event type (e.g. 'stage_transition', 'decision_rendered').
        limit: Maximum events to return (default 100).
    """
    user = _user_context_from_state(state)
    async with SessionLocal() as session:
        events = await search_events(session, days=days, event_type=event_type, limit=limit)

        if not events:
            await write_audit_event(
                session,
                event_type="query",
                user_id=user.user_id,
                user_role=user.role.value,
                event_data={
                    "tool": "ceo_audit_search",
                    "days": days,
                    "event_type": event_type,
                    "limit": limit,
                },
            )
            await session.commit()
            return "没有符合筛选条件的审计事件。"

        # Format inside session to avoid DetachedInstanceError
        lines = [f"审计检索结果（{len(events)} 条）："]
        if days:
            lines[0] += f"（近 {days} 天）"
        if event_type:
            lines[0] += f"（类型：{event_type}）"
        lines.append("")

        for evt in events[:50]:  # Cap display at 50 for readability
            ts = _format_timestamp(evt.timestamp)
            line = f"  [{ts}] {_audit_event_label(evt.event_type)}"
            if evt.application_id:
                line += f"（申请 #{evt.application_id}）"
            if evt.user_id:
                line += f"，操作人：{evt.user_id}"
            lines.append(line)

        if len(events) > 50:
            lines.append(f"  ……另有 {len(events) - 50} 条未展开")

        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={
                "tool": "ceo_audit_search",
                "days": days,
                "event_type": event_type,
                "limit": limit,
            },
        )
        await session.commit()

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Model monitoring tools (S-5-F39)
# ---------------------------------------------------------------------------


@tool
async def ceo_model_latency(
    hours: int = 24,
    model: str | None = None,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get model latency percentiles (p50, p95, p99) and trend.

    Args:
        hours: Time range in hours (default 24).
        model: Optional model name filter.
    """
    user = _user_context_from_state(state)
    try:
        summary = await get_model_monitoring_summary(hours=hours, model=model)
    except Exception as e:
        return f"获取模型监控数据失败：{e}"

    async with SessionLocal() as session:
        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={"tool": "ceo_model_latency", "hours": hours, "model": model},
        )
        await session.commit()

    if not summary.langfuse_available:
        return "模型监控暂不可用（尚未配置 Langfuse）。"

    lat = summary.latency
    lines = [
        f"模型响应时延（近 {summary.time_range_hours} 小时）：",
        f"  p50: {lat.p50_ms:.1f}ms",
        f"  p95: {lat.p95_ms:.1f}ms",
        f"  p99: {lat.p99_ms:.1f}ms",
    ]
    if lat.by_model:
        lines.append("")
        lines.append("按模型：")
        for m in lat.by_model:
            lines.append(
                f"  {m.model}：p50={m.p50_ms:.1f}ms，p95={m.p95_ms:.1f}ms（{m.call_count} 次调用）"
            )
    return "\n".join(lines)


@tool
async def ceo_model_token_usage(
    hours: int = 24,
    model: str | None = None,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get token usage totals and per-model breakdown.

    Args:
        hours: Time range in hours (default 24).
        model: Optional model name filter.
    """
    user = _user_context_from_state(state)
    try:
        summary = await get_model_monitoring_summary(hours=hours, model=model)
    except Exception as e:
        return f"获取模型监控数据失败：{e}"

    async with SessionLocal() as session:
        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={
                "tool": "ceo_model_token_usage",
                "hours": hours,
                "model": model,
            },
        )
        await session.commit()

    if not summary.langfuse_available:
        return "模型监控暂不可用（尚未配置 Langfuse）。"

    tok = summary.token_usage
    lines = [
        f"Token 使用量（近 {summary.time_range_hours} 小时）：",
        f"  输入 Token：{tok.input_tokens:,}",
        f"  输出 Token：{tok.output_tokens:,}",
        f"  总 Token：{tok.total_tokens:,}",
    ]
    if tok.by_model:
        lines.append("")
        lines.append("按模型：")
        for m in tok.by_model:
            lines.append(f"  {m.model}：{m.total_tokens:,} Token（{m.call_count} 次调用）")
    return "\n".join(lines)


@tool
async def ceo_model_errors(
    hours: int = 24,
    model: str | None = None,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get model error rates and top error types.

    Args:
        hours: Time range in hours (default 24).
        model: Optional model name filter.
    """
    user = _user_context_from_state(state)
    try:
        summary = await get_model_monitoring_summary(hours=hours, model=model)
    except Exception as e:
        return f"获取模型监控数据失败：{e}"

    async with SessionLocal() as session:
        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={"tool": "ceo_model_errors", "hours": hours, "model": model},
        )
        await session.commit()

    if not summary.langfuse_available:
        return "模型监控暂不可用（尚未配置 Langfuse）。"

    err = summary.errors
    lines = [
        f"模型错误情况（近 {summary.time_range_hours} 小时）：",
        f"  调用总数：{err.total_calls:,}",
        f"  错误数：{err.error_count:,}",
        f"  错误率：{err.error_rate}%",
    ]
    if err.top_errors:
        lines.append("")
        lines.append("主要错误类型：")
        for e in err.top_errors[:5]:
            lines.append(f"  {e.error_type}: {e.count}")
    return "\n".join(lines)


@tool
async def ceo_model_routing(
    hours: int = 24,
    model: str | None = None,
    state: Annotated[dict, InjectedState] = {},
) -> str:
    """Get model routing distribution showing which models handle what percentage of calls.

    Args:
        hours: Time range in hours (default 24).
        model: Optional model name filter.
    """
    user = _user_context_from_state(state)
    try:
        summary = await get_model_monitoring_summary(hours=hours, model=model)
    except Exception as e:
        return f"获取模型监控数据失败：{e}"

    async with SessionLocal() as session:
        await write_audit_event(
            session,
            event_type="query",
            user_id=user.user_id,
            user_role=user.role.value,
            event_data={"tool": "ceo_model_routing", "hours": hours, "model": model},
        )
        await session.commit()

    if not summary.langfuse_available:
        return "模型监控暂不可用（尚未配置 Langfuse）。"

    routing = summary.routing
    lines = [
        f"模型路由分布（近 {summary.time_range_hours} 小时）：",
        f"  调用总数：{routing.total_calls:,}",
        "",
        "分布：",
    ]
    for m in routing.models:
        lines.append(f"  {m.model}：{m.call_count:,} 次（{m.percentage}%）")
    return "\n".join(lines)
