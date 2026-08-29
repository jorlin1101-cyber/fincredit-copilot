# This project was developed with assistance from AI tools.
"""LangGraph tools for the public assistant agent.

These wrap existing business logic so the agent can call them
as tool invocations during a conversation.
"""

from datetime import date

from langchain_core.tools import tool

from ..schemas.calculator import AffordabilityRequest
from ..services.calculator import calculate_affordability
from ..services.products import PRODUCTS


@tool
def current_date() -> str:
    """Return today's date. Use this when you need the current date for due dates, timelines, or any date calculations."""
    return date.today().isoformat()


@tool
def product_info() -> str:
    """查询中国住房贷款演示产品和可核验的利率参考来源。"""
    lines = []
    for p in PRODUCTS:
        lines.append(
            f"- **{p.name}**：{p.description} 最低首付款比例参考值为"
            f"{p.min_down_payment_pct:.0f}%，测算利率为{p.typical_rate:.2f}%。"
            f"{p.rate_note} 数据日期：{p.data_as_of}。"
            f"来源：{p.source_name}（{p.source_url}）。"
        )
    return "\n".join(lines)


@tool
def affordability_calc(
    gross_annual_income: float,
    monthly_debts: float = 0,
    monthly_property_fee: float = 0,
    down_payment: float = 0,
    interest_rate: float = 3.5,
    loan_term_years: int = 30,
) -> str:
    """按中国审慎偿债口径测算商业住房贷款购房预算（人民币）。

    Args:
        gross_annual_income: 家庭税前年收入，单位为人民币元。
        monthly_debts: 其他债务月均偿付额，单位为人民币元。
        monthly_property_fee: 月物业管理费，单位为人民币元。
        down_payment: 可用首付款，单位为人民币元。
        interest_rate: 年利率参考值，默认 3.5%，不代表银行实际报价。
        loan_term_years: 贷款年限，默认 30 年。
    """
    req = AffordabilityRequest(
        gross_annual_income=gross_annual_income,
        monthly_debts=monthly_debts,
        monthly_property_fee=monthly_property_fee,
        down_payment=down_payment,
        interest_rate=interest_rate,
        loan_term_years=loan_term_years,
    )
    result = calculate_affordability(req)

    parts = [
        f"最高参考贷款额：¥{result.max_loan_amount:,.2f}",
        f"预计月供：¥{result.estimated_monthly_payment:,.2f}",
        f"参考购房总价：¥{result.estimated_purchase_price:,.2f}",
        f"总债务收入比：{result.dti_ratio}%",
        f"住房支出收入比：{result.housing_expense_ratio}%",
        f"LTV：{result.ltv_ratio}%",
    ]
    if result.dti_warning:
        parts.append(f"提示：{result.dti_warning}")
    parts.append("本结果仅作辅助测算，不构成银行授信审批或贷款承诺。")
    return "\n".join(parts)
