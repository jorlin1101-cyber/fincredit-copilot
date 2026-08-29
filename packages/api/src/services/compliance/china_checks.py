# This project was developed with assistance from AI tools.
"""China housing-credit compliance checks used by the public demo workflow.

These checks deliberately separate binding public-policy evidence from internal
demo review thresholds. They provide review prompts only and never make a final
credit decision.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from .checks import ComplianceCheckResult, ComplianceStatus, run_all_checks

_CHENGDU_NEW_HOME_POLICY_START = date(2026, 8, 25)
_CHENGDU_NEW_HOME_POLICY_END = date(2026, 12, 31)
_MINIMUM_DOWN_PAYMENT_RATIO = Decimal("0.15")


def check_material_authenticity(
    *,
    has_identity_docs: bool,
    has_income_docs: bool,
    has_asset_docs: bool,
) -> ComplianceCheckResult:
    """Check whether core identity, income and asset evidence is available."""
    missing: list[str] = []
    if not has_identity_docs:
        missing.append("缺少有效身份证明，无法完成申请人身份核验。")
    if not has_income_docs:
        missing.append("缺少收入证明或纳税记录，无法核验收入来源。")
    if not has_asset_docs:
        missing.append("缺少银行流水，无法核验首付款来源和资产情况。")

    if not has_identity_docs or not has_income_docs:
        return ComplianceCheckResult(
            regulation="申请材料与尽职调查",
            status=ComplianceStatus.FAIL,
            rationale="核心身份或收入材料缺失，须补充后再进入审批。",
            details=missing,
        )
    if missing:
        return ComplianceCheckResult(
            regulation="申请材料与尽职调查",
            status=ComplianceStatus.WARNING,
            rationale="核心材料已提供，但资产核验材料仍需补充或人工复核。",
            details=missing,
        )
    return ComplianceCheckResult(
        regulation="申请材料与尽职调查",
        status=ComplianceStatus.PASS,
        rationale="身份、收入和资产类核心材料均已提供，可继续人工核验。",
        details=["系统仅核验材料可用性；真实性、完整性及原件一致性仍须人工确认。"],
    )


def check_repayment_ability(
    *,
    dti: float | None,
    has_income_docs: bool,
    has_asset_docs: bool,
) -> ComplianceCheckResult:
    """Assess repayment evidence without treating a demo DTI line as law."""
    details: list[str] = []
    if dti is None:
        return ComplianceCheckResult(
            regulation="还款能力评估",
            status=ComplianceStatus.FAIL,
            rationale="现有数据不足，无法计算债务收入比。",
            details=["须补充可核验的月收入及月负债数据。"],
        )

    details.append(f"债务收入比（DTI）为 {dti:.1%}。")
    details.append("DTI 仅作为本项目内部辅助指标，不是全国统一的法定拒贷阈值。")
    if not has_income_docs:
        details.append("缺少可核验的收入材料。")
    if not has_asset_docs:
        details.append("缺少银行流水等资产材料。")

    if not has_income_docs:
        return ComplianceCheckResult(
            regulation="还款能力评估",
            status=ComplianceStatus.FAIL,
            rationale="缺少收入证明，不能仅依据录入数值判断还款能力。",
            details=details,
        )
    if dti > 0.50:
        return ComplianceCheckResult(
            regulation="还款能力评估",
            status=ComplianceStatus.CONDITIONAL_PASS,
            rationale="超过内部演示复核线，必须由有权审批人员重点复核。",
            details=details,
        )
    if not has_asset_docs:
        return ComplianceCheckResult(
            regulation="还款能力评估",
            status=ComplianceStatus.WARNING,
            rationale="收入数据可计算，但资产和首付款来源证据不完整。",
            details=details,
        )
    return ComplianceCheckResult(
        regulation="还款能力评估",
        status=ComplianceStatus.PASS,
        rationale="当前收入、负债及资产材料支持继续人工审批。",
        details=details,
    )


def check_housing_credit_policy(
    *,
    loan_amount: Decimal | float | None,
    property_value: Decimal | float | None,
    application_date: date,
) -> ComplianceCheckResult:
    """Check the public 15% minimum down-payment baseline and Chengdu scope."""
    try:
        loan = Decimal(str(loan_amount)) if loan_amount is not None else None
        value = Decimal(str(property_value)) if property_value is not None else None
    except (InvalidOperation, TypeError, ValueError):
        loan = None
        value = None

    if loan is None or value is None or value <= 0:
        return ComplianceCheckResult(
            regulation="全国及成都住房信贷政策",
            status=ComplianceStatus.WARNING,
            rationale="缺少贷款金额或房产价值，无法核验首付款比例。",
            details=["须补全金额，并人工确认贷款产品、房屋类型和政策适用日期。"],
        )

    down_payment_ratio = (value - loan) / value
    details = [
        f"按录入金额计算，首付款比例为 {down_payment_ratio:.1%}。",
        "全国商业性个人住房贷款最低首付款比例基准为不低于15%，各地和具体产品可另有要求。",
    ]

    if _CHENGDU_NEW_HOME_POLICY_START <= application_date <= _CHENGDU_NEW_HOME_POLICY_END:
        details.append(
            "申请日期处于成都市2026年阶段性政策期内；购买新建住房的住房公积金贷款"
            "最低首付款比例为15%，须人工确认房屋及贷款产品类型。"
        )
    else:
        details.append("须按申请日期检索当期成都市地方规则并核验适用性。")

    if down_payment_ratio < _MINIMUM_DOWN_PAYMENT_RATIO:
        return ComplianceCheckResult(
            regulation="全国及成都住房信贷政策",
            status=ComplianceStatus.FAIL,
            rationale="当前首付款比例低于15%的公开政策基准。",
            details=details,
        )

    return ComplianceCheckResult(
        regulation="全国及成都住房信贷政策",
        status=ComplianceStatus.CONDITIONAL_PASS,
        rationale="金额比例满足15%基准，仍须人工确认具体产品及地方政策适用性。",
        details=details,
    )


def run_china_checks(
    material: ComplianceCheckResult,
    repayment: ComplianceCheckResult,
    policy: ComplianceCheckResult,
) -> dict:
    """Combine the three active China-scenario checks."""
    return run_all_checks(material, repayment, policy)
