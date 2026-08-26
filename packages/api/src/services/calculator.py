# This project was developed with assistance from AI tools.
"""China commercial housing loan affordability calculation logic.

Pure math, no I/O. Shared by the public API route and the agent tool.
"""

from ..schemas.calculator import AffordabilityRequest, AffordabilityResponse

HOUSING_EXPENSE_RATIO_LIMIT = 0.50
TOTAL_DEBT_RATIO_LIMIT = 0.55
MINIMUM_DOWN_PAYMENT_RATIO = 0.15


def compute_monthly_payment(principal: float, annual_rate: float, term_months: int) -> float:
    """Compute monthly payment for a loan.

    Uses the standard amortization formula. Returns 0 for invalid inputs.

    Args:
        principal: The loan amount in renminbi.
        annual_rate: Annual interest rate as a percentage (e.g., 6.875 for 6.875%).
        term_months: Loan term in months.

    Returns:
        Monthly payment amount in renminbi.
    """
    if principal <= 0 or term_months <= 0:
        return 0.0

    monthly_rate = annual_rate / 100 / 12
    if monthly_rate <= 0:
        return principal / term_months

    compound = (1 + monthly_rate) ** term_months
    return principal * (monthly_rate * compound) / (compound - 1)


def calculate_affordability(req: AffordabilityRequest) -> AffordabilityResponse:
    """Estimate a commercial housing purchase budget using Chinese prudential ratios.

    The repayment cap applies both the 50% housing-expense ratio and the 55%
    total-debt ratio. The purchase budget also observes the national 15% minimum
    down-payment floor. Local regulators and lenders may apply stricter rules.
    """
    gross_monthly_income = req.gross_annual_income / 12
    housing_payment_cap = (
        gross_monthly_income * HOUSING_EXPENSE_RATIO_LIMIT - req.monthly_property_fee
    )
    total_debt_payment_cap = (
        gross_monthly_income * TOTAL_DEBT_RATIO_LIMIT - req.monthly_property_fee - req.monthly_debts
    )
    max_housing_payment = max(0.0, min(housing_payment_cap, total_debt_payment_cap))

    if max_housing_payment <= 0:
        existing_dti = (req.monthly_debts + req.monthly_property_fee) / gross_monthly_income * 100
        return AffordabilityResponse(
            max_loan_amount=0,
            estimated_monthly_payment=0,
            estimated_purchase_price=0,
            dti_ratio=round(existing_dti, 1),
            housing_expense_ratio=round(req.monthly_property_fee / gross_monthly_income * 100, 1),
            ltv_ratio=0,
            down_payment_ratio=0,
            housing_payment_cap=round(max(0.0, housing_payment_cap), 2),
            total_debt_payment_cap=round(max(0.0, total_debt_payment_cap), 2),
            binding_constraint="repayment_capacity",
            dti_warning=(
                "现有月债务与物业费已达到审慎偿债能力上限，当前输入下不建议新增住房贷款。"
            ),
        )

    monthly_rate = req.interest_rate / 100 / 12
    n_payments = req.loan_term_years * 12

    if monthly_rate > 0:
        compound = (1 + monthly_rate) ** n_payments
        payment_per_yuan = monthly_rate * compound / (compound - 1)
    else:
        payment_per_yuan = 1 / n_payments

    repayment_capacity_loan = max_housing_payment / payment_per_yuan
    repayment_capacity_price = repayment_capacity_loan + req.down_payment
    down_payment_capacity_price = (
        req.down_payment / MINIMUM_DOWN_PAYMENT_RATIO if req.down_payment > 0 else 0
    )

    estimated_purchase_price = min(repayment_capacity_price, down_payment_capacity_price)
    max_loan_amount = max(0.0, estimated_purchase_price - req.down_payment)
    estimated_monthly_payment = compute_monthly_payment(
        max_loan_amount, req.interest_rate, n_payments
    )
    binding_constraint = (
        "down_payment"
        if down_payment_capacity_price <= repayment_capacity_price
        else "repayment_capacity"
    )

    housing_monthly_obligations = estimated_monthly_payment + req.monthly_property_fee
    total_monthly_obligations = housing_monthly_obligations + req.monthly_debts
    housing_expense_ratio = round(housing_monthly_obligations / gross_monthly_income * 100, 1)
    dti_ratio = round(total_monthly_obligations / gross_monthly_income * 100, 1)
    ltv_ratio = (
        round(max_loan_amount / estimated_purchase_price * 100, 1)
        if estimated_purchase_price > 0
        else 0
    )
    down_payment_ratio = (
        round(req.down_payment / estimated_purchase_price * 100, 1)
        if estimated_purchase_price > 0
        else 0
    )

    dti_warning = None
    if req.down_payment <= 0:
        dti_warning = "首付款为 0，未达到商业性个人住房贷款最低首付比例要求。"

    return AffordabilityResponse(
        max_loan_amount=round(max_loan_amount, 2),
        estimated_monthly_payment=round(estimated_monthly_payment, 2),
        estimated_purchase_price=round(estimated_purchase_price, 2),
        dti_ratio=dti_ratio,
        housing_expense_ratio=housing_expense_ratio,
        ltv_ratio=ltv_ratio,
        down_payment_ratio=down_payment_ratio,
        housing_payment_cap=round(max(0.0, housing_payment_cap), 2),
        total_debt_payment_cap=round(max(0.0, total_debt_payment_cap), 2),
        binding_constraint=binding_constraint,
        dti_warning=dti_warning,
        pmi_warning=None,
    )
