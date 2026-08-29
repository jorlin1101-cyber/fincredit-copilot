# This project was developed with assistance from AI tools.
"""Unit tests for the active nationwide + Chengdu compliance checks."""

from datetime import date

from src.services.compliance.checks import ComplianceStatus
from src.services.compliance.china_checks import (
    check_housing_credit_policy,
    check_material_authenticity,
    check_repayment_ability,
    run_china_checks,
)


def test_material_check_requires_identity_and_income() -> None:
    result = check_material_authenticity(
        has_identity_docs=False,
        has_income_docs=True,
        has_asset_docs=True,
    )
    assert result.status == ComplianceStatus.FAIL
    assert "身份证明" in result.details[0]


def test_repayment_threshold_is_labelled_internal_review_line() -> None:
    result = check_repayment_ability(
        dti=0.51,
        has_income_docs=True,
        has_asset_docs=True,
    )
    assert result.status == ComplianceStatus.CONDITIONAL_PASS
    assert "内部演示复核线" in result.rationale
    assert any("不是全国统一的法定拒贷阈值" in detail for detail in result.details)


def test_chengdu_policy_fails_down_payment_below_fifteen_percent() -> None:
    result = check_housing_credit_policy(
        loan_amount=860_000,
        property_value=1_000_000,
        application_date=date(2026, 8, 28),
    )
    assert result.status == ComplianceStatus.FAIL
    assert any("成都市2026年阶段性政策期" in detail for detail in result.details)


def test_chengdu_policy_requires_human_scope_confirmation_at_baseline() -> None:
    material = check_material_authenticity(
        has_identity_docs=True,
        has_income_docs=True,
        has_asset_docs=True,
    )
    repayment = check_repayment_ability(
        dti=0.36,
        has_income_docs=True,
        has_asset_docs=True,
    )
    policy = check_housing_credit_policy(
        loan_amount=850_000,
        property_value=1_000_000,
        application_date=date(2026, 8, 28),
    )
    combined = run_china_checks(material, repayment, policy)

    assert policy.status == ComplianceStatus.CONDITIONAL_PASS
    assert combined["overall_status"] == ComplianceStatus.CONDITIONAL_PASS
    assert combined["can_proceed"] is True
