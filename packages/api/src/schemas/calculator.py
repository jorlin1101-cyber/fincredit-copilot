# This project was developed with assistance from AI tools.
"""Affordability calculator schemas."""

from pydantic import BaseModel, Field


class AffordabilityRequest(BaseModel):
    """Input for the China commercial housing loan affordability calculator."""

    gross_annual_income: float = Field(gt=0)
    monthly_debts: float = Field(ge=0)
    monthly_property_fee: float = Field(default=0, ge=0)
    down_payment: float = Field(ge=0)
    interest_rate: float = Field(default=3.5, ge=0, le=15)
    loan_term_years: int = Field(default=30, ge=10, le=40)


class AffordabilityResponse(BaseModel):
    """Transparent affordability calculation results in renminbi."""

    max_loan_amount: float
    estimated_monthly_payment: float
    estimated_purchase_price: float
    dti_ratio: float
    housing_expense_ratio: float
    ltv_ratio: float
    down_payment_ratio: float
    housing_payment_cap: float
    total_debt_payment_cap: float
    binding_constraint: str
    minimum_down_payment_ratio: float = 15.0
    dti_warning: str | None = None
    # Kept for backward compatibility with older clients. China has no US-style PMI rule.
    pmi_warning: str | None = None
