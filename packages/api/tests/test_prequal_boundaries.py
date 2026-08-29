# This project was developed with assistance from AI tools.
"""Boundary tests for pre-qualification eligibility thresholds.

Verifies that >= and > comparisons at exact product eligibility boundaries
produce the correct eligible/ineligible classification. Off-by-one errors
in threshold checks are the most common bug in eligibility logic.
"""

from decimal import Decimal

import pytest

from src.services.prequalification import evaluate_prequalification


def _is_eligible(result, product_id: str) -> bool:
    return any(p.product_id == product_id for p in result.eligible_products)


def _is_ineligible(result, product_id: str) -> bool:
    return any(p.product_id == product_id for p in result.ineligible_products)


# Shared baseline: all values well within limits so we can isolate one variable
_BASELINE = dict(
    gross_monthly_income=Decimal("10000"),
    monthly_debts=Decimal("500"),
    loan_amount=Decimal("200000"),
    property_value=Decimal("400000"),  # 50% LTV, well under all limits
)


class TestCreditScoreBoundaries:
    """Credit score uses strict `<` comparison: score < min is ineligible."""

    def test_conventional_at_exactly_600_is_eligible(self):
        result = evaluate_prequalification(
            credit_score=600,
            **_BASELINE,
            loan_type="conventional_30",
        )
        assert _is_eligible(result, "conventional_30")

    def test_conventional_at_599_is_ineligible(self):
        result = evaluate_prequalification(
            credit_score=599,
            **_BASELINE,
            loan_type="conventional_30",
        )
        assert _is_ineligible(result, "conventional_30")

    def test_fha_at_exactly_580_is_eligible(self):
        result = evaluate_prequalification(
            credit_score=580,
            **_BASELINE,
            loan_type="fha",
        )
        assert _is_eligible(result, "fha")

    def test_fha_at_579_is_ineligible(self):
        result = evaluate_prequalification(
            credit_score=579,
            **_BASELINE,
            loan_type="fha",
        )
        assert _is_ineligible(result, "fha")

    def test_jumbo_at_exactly_680_is_eligible(self):
        result = evaluate_prequalification(
            credit_score=680,
            **_BASELINE,
            loan_type="jumbo",
        )
        assert _is_eligible(result, "jumbo")

    def test_jumbo_at_679_is_ineligible(self):
        result = evaluate_prequalification(
            credit_score=679,
            **_BASELINE,
            loan_type="jumbo",
        )
        assert _is_ineligible(result, "jumbo")

    def test_county_demo_at_exactly_600_is_eligible(self):
        result = evaluate_prequalification(
            credit_score=600,
            **_BASELINE,
            loan_type="usda",
        )
        assert _is_eligible(result, "usda")

    def test_county_demo_at_599_is_ineligible(self):
        result = evaluate_prequalification(
            credit_score=599,
            **_BASELINE,
            loan_type="usda",
        )
        assert _is_ineligible(result, "usda")


class TestLtvBoundaries:
    """LTV uses strict `>` comparison: ltv_pct > max is ineligible."""

    def test_jumbo_at_exactly_80pct_ltv_is_eligible(self):
        """¥320K / ¥400K = 80.0% LTV, large-loan demo max is 80%."""
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("15000"),
            monthly_debts=Decimal("500"),
            loan_amount=Decimal("320000"),
            property_value=Decimal("400000"),
            loan_type="jumbo",
        )
        assert _is_eligible(result, "jumbo")

    def test_jumbo_at_80_point_1_pct_ltv_is_ineligible(self):
        """¥320400 / ¥400000 = 80.1% LTV, above the internal demo line."""
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("15000"),
            monthly_debts=Decimal("500"),
            loan_amount=Decimal("320400"),
            property_value=Decimal("400000"),
            loan_type="jumbo",
        )
        assert _is_ineligible(result, "jumbo")

    def test_lpr_floating_at_exactly_85pct_ltv_is_eligible(self):
        """¥340K / ¥400K = 85.0% LTV, matching the 15% baseline down payment."""
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("15000"),
            monthly_debts=Decimal("500"),
            loan_amount=Decimal("340000"),
            property_value=Decimal("400000"),
            loan_type="arm",
        )
        assert _is_eligible(result, "arm")

    def test_commercial_at_exactly_85pct_ltv_is_eligible(self):
        """¥340K / ¥400K = 85.0% LTV, matching the 15% baseline down payment."""
        result = evaluate_prequalification(
            credit_score=750,
            gross_monthly_income=Decimal("15000"),
            monthly_debts=Decimal("500"),
            loan_amount=Decimal("340000"),
            property_value=Decimal("400000"),
            loan_type="conventional_30",
        )
        assert _is_eligible(result, "conventional_30")


class TestMultipleConstraintsAtLimits:
    """All thresholds simultaneously at their limits."""

    @pytest.mark.parametrize(
        "credit_score,loan_type,expected",
        [
            (600, "conventional_30", True),
            (599, "conventional_30", False),
            (580, "fha", True),
            (579, "fha", False),
        ],
    )
    def test_credit_at_boundary_with_moderate_financials(self, credit_score, loan_type, expected):
        """Credit score at boundary with moderate DTI and LTV."""
        result = evaluate_prequalification(
            credit_score=credit_score,
            gross_monthly_income=Decimal("8000"),
            monthly_debts=Decimal("1000"),
            loan_amount=Decimal("300000"),
            property_value=Decimal("400000"),
            loan_type=loan_type,
        )
        if expected:
            assert _is_eligible(result, loan_type)
        else:
            assert _is_ineligible(result, loan_type)

    def test_all_products_boundary_split(self):
        """At the internal 600 line, all demo products except large-loan match."""
        result = evaluate_prequalification(
            credit_score=600,
            **_BASELINE,
        )
        assert _is_eligible(result, "conventional_30")
        assert _is_eligible(result, "arm")
        assert _is_eligible(result, "fha")
        assert _is_eligible(result, "va")
        assert _is_eligible(result, "usda")
        assert _is_ineligible(result, "jumbo")
