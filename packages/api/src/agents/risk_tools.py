# This project was developed with assistance from AI tools.
"""Risk assessment helpers for underwriting.

Pure functions for computing risk factors from application data.
Called by underwriter_tools.py.
"""

from dataclasses import dataclass

from db.enums import EmploymentStatus


@dataclass
class RiskAssessment:
    """Risk assessment result with typed factor fields."""

    dti: dict[str, float | str | None]
    ltv: dict[str, float | str | None]
    credit: dict[str, int | str | None]
    income_stability: dict[str, str | None]
    asset_sufficiency: dict[str, float | str | None]
    compensating_factors: list[str]
    warnings: list[str]


@dataclass
class Recommendation:
    """Preliminary underwriting recommendation derived from risk factors."""

    recommendation: str
    rationale: list[str]
    conditions: list[str]


_RISK_LOW = "低"
_RISK_MEDIUM = "中"
_RISK_HIGH = "高"


def compute_risk_factors(
    app, financials_rows, borrowers, *, bureau_credit_score: int | None = None
) -> RiskAssessment:
    """Compute risk factors from application data.

    Pure function -- no DB access.  Returns a RiskAssessment dataclass with:
      dti, ltv, credit, income_stability, asset_sufficiency,
      compensating_factors, warnings
    Each factor has: value, rating, notes.

    If ``bureau_credit_score`` is provided (from a hard-pull CreditReport),
    it takes precedence over self-reported scores in financials_rows.
    """
    warnings: list[str] = []

    # --- DTI ---
    total_income = sum(float(f.gross_monthly_income or 0) for f in financials_rows)
    total_debts = sum(float(f.monthly_debts or 0) for f in financials_rows)
    if total_income > 0:
        dti_pct = total_debts / total_income * 100
        if dti_pct <= 40:
            dti_rating = _RISK_LOW
        elif dti_pct <= 50:
            dti_rating = _RISK_MEDIUM
        else:
            dti_rating = _RISK_HIGH
        dti = {"value": round(dti_pct, 1), "rating": dti_rating}
    else:
        dti = {"value": None, "rating": None}
        warnings.append("缺少收入数据，无法计算债务收入比")

    # --- LTV ---
    loan_amount = float(app.loan_amount or 0)
    property_value = float(app.property_value or 0)
    if property_value > 0 and loan_amount > 0:
        ltv_pct = loan_amount / property_value * 100
        if ltv_pct <= 70:
            ltv_rating = _RISK_LOW
        elif ltv_pct <= 85:
            ltv_rating = _RISK_MEDIUM
        else:
            ltv_rating = _RISK_HIGH
        ltv = {"value": round(ltv_pct, 1), "rating": ltv_rating}
    else:
        ltv = {"value": None, "rating": None}
        warnings.append("缺少贷款金额或房产价值，无法计算贷款成数")

    # --- Credit score ---
    # Prefer bureau score from hard-pull CreditReport over self-reported
    if bureau_credit_score is not None:
        min_score = bureau_credit_score
    else:
        credit_scores = [f.credit_score for f in financials_rows if f.credit_score]
        min_score = min(credit_scores) if credit_scores else None

    if min_score is not None:
        if min_score > 700:
            credit_rating = _RISK_LOW
        elif min_score >= 600:
            credit_rating = _RISK_MEDIUM
        else:
            credit_rating = _RISK_HIGH
        credit = {"value": min_score, "rating": credit_rating}
    else:
        credit = {"value": None, "rating": None}
        warnings.append("尚无可用的模拟征信评分")

    # --- Income stability ---
    emp_statuses = []
    for b_info in borrowers:
        emp = b_info.get("employment_status")
        if emp:
            emp_statuses.append(emp)

    if emp_statuses:
        stability_map = {
            EmploymentStatus.W2_EMPLOYEE.value: _RISK_LOW,
            EmploymentStatus.RETIRED.value: _RISK_LOW,
            EmploymentStatus.SELF_EMPLOYED.value: _RISK_MEDIUM,
            EmploymentStatus.OTHER.value: _RISK_MEDIUM,
            EmploymentStatus.UNEMPLOYED.value: _RISK_HIGH,
        }
        ratings = [stability_map.get(e, _RISK_MEDIUM) for e in emp_statuses]
        risk_order = {_RISK_LOW: 0, _RISK_MEDIUM: 1, _RISK_HIGH: 2}
        worst_rating = max(ratings, key=lambda r: risk_order.get(r, 1))
        income_stability = {"value": ", ".join(emp_statuses), "rating": worst_rating}
    else:
        income_stability = {"value": None, "rating": None}
        warnings.append("尚未填写就业状态")

    # --- Asset sufficiency ---
    total_assets = sum(float(f.total_assets or 0) for f in financials_rows)
    if loan_amount > 0 and total_assets > 0:
        asset_ratio = total_assets / loan_amount * 100
        if asset_ratio > 20:
            asset_rating = _RISK_LOW
        elif asset_ratio >= 10:
            asset_rating = _RISK_MEDIUM
        else:
            asset_rating = _RISK_HIGH
        asset_sufficiency = {"value": round(asset_ratio, 1), "rating": asset_rating}
    else:
        asset_sufficiency = {"value": None, "rating": None}
        if total_assets == 0:
            warnings.append("尚无可核验的资产数据")

    # --- Compensating factors ---
    comp_factors: list[str] = []
    if credit.get("value") and credit["value"] > 740 and dti.get("rating") == _RISK_HIGH:
        comp_factors.append("模拟征信评分较高，可作为人工复核债务负担时的补充信息")
    if ltv.get("value") and ltv["value"] < 60 and credit.get("rating") == _RISK_HIGH:
        comp_factors.append("贷款成数较低，可作为人工复核信用风险时的补充信息")
    if asset_sufficiency.get("value") and asset_sufficiency["value"] > 50:
        comp_factors.append("已录入资产相对贷款金额较充足，仍须核验资金来源")

    return RiskAssessment(
        dti=dti,
        ltv=ltv,
        credit=credit,
        income_stability=income_stability,
        asset_sufficiency=asset_sufficiency,
        compensating_factors=comp_factors,
        warnings=warnings,
    )


def extract_borrower_info(app) -> list[dict]:
    """Extract borrower employment info from an application's borrowers."""
    borrowers = []
    for ab in app.application_borrowers or []:
        if ab.borrower:
            b = ab.borrower
            emp = (
                b.employment_status.value
                if b.employment_status and hasattr(b.employment_status, "value")
                else str(b.employment_status)
                if b.employment_status
                else None
            )
            borrowers.append(
                {
                    "name": f"{b.first_name} {b.last_name}",
                    "is_primary": ab.is_primary,
                    "employment_status": emp,
                }
            )
    return borrowers


def compute_recommendation(
    risk: RiskAssessment,
    borrowers: list[dict],
    has_financials: bool,
    doc_total: int,
) -> Recommendation:
    """Derive an advisory workflow recommendation with a human decision boundary."""
    recommendation = "可提交人工决策"
    rationale: list[str] = []
    conditions_list: list[str] = []

    dti_val = risk.dti.get("value")
    ltv_val = risk.ltv.get("value")
    credit_val = risk.credit.get("value")

    review_reasons: list[str] = []
    if dti_val is not None and dti_val > 55:
        review_reasons.append(f"债务收入比为 {dti_val}%，超过项目内部重点复核线 55%")
    if credit_val is not None and credit_val < 600:
        review_reasons.append(f"模拟征信评分为 {credit_val}，低于项目内部重点复核线 600")
    if ltv_val is not None and ltv_val > 85:
        review_reasons.append(f"贷款成数为 {ltv_val}%，须重点核验首付款比例和适用产品政策")

    emp_statuses = [b.get("employment_status") for b in borrowers if b.get("employment_status")]
    has_employed = any(
        e in (EmploymentStatus.W2_EMPLOYEE.value, EmploymentStatus.SELF_EMPLOYED.value)
        for e in emp_statuses
    )
    if EmploymentStatus.UNEMPLOYED.value in emp_statuses and not has_employed:
        review_reasons.append("借款人当前无稳定就业记录，须核验其他持续收入和还款来源")

    if not has_financials:
        recommendation = "需补充材料"
        rationale = ["缺少财务数据，无法完成风险辅助评估"]
    elif credit_val is None:
        recommendation = "需补充材料"
        rationale = ["缺少模拟征信评分，需先完成授权范围内的征信核验"]
    elif doc_total == 0:
        recommendation = "需补充材料"
        rationale = ["尚无申请材料，无法核验借款人信息"]
    else:
        if dti_val is not None and 50 < dti_val <= 55:
            conditions_list.append(
                f"债务收入比为 {dti_val}%，超过项目内部常规复核线，须补充还款能力说明"
            )
        if ltv_val is not None and ltv_val > 85:
            conditions_list.append("核验首付款比例、房屋类型和申请日有效的全国及成都政策")
        if credit_val is not None and 600 <= credit_val < 650:
            conditions_list.append(
                f"模拟征信评分为 {credit_val}，须结合负债、履约记录和收入材料综合复核"
            )
        if EmploymentStatus.SELF_EMPLOYED.value in emp_statuses:
            conditions_list.append("自雇借款人须核验纳税记录、经营流水和持续经营情况")

        if review_reasons or conditions_list:
            recommendation = "需重点人工复核"
            rationale = review_reasons or [f"共有 {len(conditions_list)} 项事项需要人工确认"]
        else:
            rationale = ["关键数据要素已具备，可提交有权审批人员作出最终决定"]

    return Recommendation(
        recommendation=recommendation,
        rationale=rationale,
        conditions=conditions_list,
    )
