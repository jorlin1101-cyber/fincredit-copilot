# This project was developed with assistance from AI tools.
"""China-scenario housing-loan confirmation text helpers."""

from datetime import UTC, datetime

from db import ApplicationBorrower, Borrower
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..services.calculator import compute_monthly_payment
from ..services.rate_lock import get_rate_lock_status
from .shared import format_enum_label

_LPR_SOURCE = "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"
_LOAN_TYPE_LABELS = {
    "conventional_30": "30年期商业性个人住房贷款",
    "conventional_15": "15年期商业性个人住房贷款",
    "fha": "住房公积金个人住房贷款",
    "va": "商业贷款与公积金组合贷款",
    "jumbo": "大额商业性个人住房贷款",
    "usda": "县域住房贷款（演示产品）",
    "arm": "LPR浮动利率个人住房贷款",
}


def _person_name(first_name: str, last_name: str) -> str:
    if any("\u4e00" <= char <= "\u9fff" for char in f"{first_name}{last_name}"):
        return f"{last_name}{first_name}"
    return f"{first_name} {last_name}"


async def get_primary_borrower_name(session: AsyncSession, application_id: int) -> str:
    """Fetch the primary borrower's name for an application.

    Returns a Chinese fallback when no borrower is found.
    """
    ab_stmt = select(ApplicationBorrower).where(
        ApplicationBorrower.application_id == application_id,
        ApplicationBorrower.is_primary.is_(True),
    )
    ab_result = await session.execute(ab_stmt)
    ab = ab_result.scalar_one_or_none()
    if ab:
        b_stmt = select(Borrower).where(Borrower.id == ab.borrower_id)
        b_result = await session.execute(b_stmt)
        borrower = b_result.scalar_one_or_none()
        if borrower:
            return _person_name(borrower.first_name, borrower.last_name)
    return "借款人"


async def generate_le_text(session, user, app, application_id: int) -> str:
    """Generate a Chinese demo personal-housing-loan terms confirmation."""
    borrower_name = await get_primary_borrower_name(session, application_id)
    rate_lock = await get_rate_lock_status(session, user, application_id)

    loan_amount = float(app.loan_amount) if app.loan_amount else 0
    property_value = float(app.property_value) if app.property_value else 0
    rate = 3.5
    rate_basis = "2026年8月20日五年期以上LPR测算参考"
    if rate_lock and rate_lock.get("locked_rate"):
        rate = float(rate_lock["locked_rate"])
        rate_basis = "申请记录中的已锁定执行利率"

    loan_type = app.loan_type.value if app.loan_type else "conventional_30"
    term_years = 15 if loan_type == "conventional_15" else 30
    num_payments = term_years * 12
    monthly_payment = compute_monthly_payment(loan_amount, rate, num_payments)
    today = datetime.now(UTC).astimezone().strftime("%Y年%m月%d日")
    lines = [
        "个人住房贷款要素确认书（演示）",
        "==============================",
        f"生成日期：{today}",
        f"借款人：{borrower_name}",
        f"申请编号：#{application_id}",
        f"房产地址：{app.property_address or '待补充'}",
        "",
        "贷款要素：",
        f"  贷款金额：¥{loan_amount:,.2f}",
        f"  测算利率：{rate:.3f}%（{rate_basis}）",
        f"  贷款类型：{_LOAN_TYPE_LABELS.get(loan_type, format_enum_label(loan_type))}",
        f"  贷款期限：{term_years} 年（共 {num_payments} 期）",
        f"  等额本息月供测算：¥{monthly_payment:,.2f}",
        "",
        "费用核对：",
        "  评估、抵押登记、保险及其他费用：待受理机构或第三方出具正式报价后确认",
        "  本项目不使用无来源的固定收费比例生成费用结论。",
    ]

    if property_value > 0:
        down_payment = property_value - loan_amount
        ltv = loan_amount / property_value * 100
        lines.extend(
            [
                "",
                "首付款核对：",
                f"  房产价值：¥{property_value:,.2f}",
                f"  首付款金额：¥{down_payment:,.2f}",
                f"  贷款成数：{ltv:.1f}%",
            ]
        )

    lines.extend(
        [
            "",
            f"利率参考来源：全国银行间同业拆借中心受权公布LPR公告（{_LPR_SOURCE}）。",
            "提示：本文件仅用于虚构项目演示，不构成贷款合同、收费承诺或授信决定；",
            "实际执行利率、还款计划和费用以有权机构正式合同、价目公示及有效凭证为准。",
        ]
    )

    return "\n".join(lines)


async def generate_cd_text(session, user, app, application_id: int) -> str:
    """Generate a Chinese demo signing-elements confirmation text."""
    borrower_name = await get_primary_borrower_name(session, application_id)
    rate_lock = await get_rate_lock_status(session, user, application_id)

    loan_amount = float(app.loan_amount) if app.loan_amount else 0
    property_value = float(app.property_value) if app.property_value else 0
    rate = 3.5
    rate_basis = "2026年8月20日五年期以上LPR测算参考"
    if rate_lock and rate_lock.get("locked_rate"):
        rate = float(rate_lock["locked_rate"])
        rate_basis = "申请记录中的已锁定执行利率"

    loan_type = app.loan_type.value if app.loan_type else "conventional_30"
    term_years = 15 if loan_type == "conventional_15" else 30
    num_payments = term_years * 12
    monthly_payment = compute_monthly_payment(loan_amount, rate, num_payments)
    today = datetime.now(UTC).astimezone().strftime("%Y年%m月%d日")
    closing_date = app.closing_date.strftime("%Y年%m月%d日") if app.closing_date else "待确认"

    lines = [
        "个人住房贷款签约要素确认书（演示）",
        "==================================",
        f"生成日期：{today}",
        f"拟签约日期：{closing_date}",
        f"借款人：{borrower_name}",
        f"申请编号：#{application_id}",
        f"房产地址：{app.property_address or '待补充'}",
        "",
        "拟签约贷款要素：",
        f"  贷款金额：¥{loan_amount:,.2f}",
        f"  测算利率：{rate:.3f}%（{rate_basis}）",
        f"  贷款类型：{_LOAN_TYPE_LABELS.get(loan_type, format_enum_label(loan_type))}",
        f"  贷款期限：{term_years} 年（共 {num_payments} 期）",
        f"  等额本息月供测算：¥{monthly_payment:,.2f}",
        "",
        "签约前费用核对：",
        "  贷款相关收费、评估费、抵押登记费及第三方费用：以正式合同、价目公示",
        "  和有效票据逐项核对；演示系统不代替收费确认。",
    ]

    if property_value > 0:
        down_payment = property_value - loan_amount
        lines.extend(
            [
                "",
                "交易金额核对：",
                f"  房产价值：¥{property_value:,.2f}",
                f"  首付款金额：¥{down_payment:,.2f}",
            ]
        )

    lines.extend(
        [
            "",
            f"利率参考来源：全国银行间同业拆借中心受权公布LPR公告（{_LPR_SOURCE}）。",
            "提示：本文件仅用于虚构项目演示，不构成贷款合同、收费承诺或授信决定；",
            "正式签约前必须由借款人与有权机构逐项核对合同、还款计划、费用和风险提示。",
        ]
    )

    return "\n".join(lines)
