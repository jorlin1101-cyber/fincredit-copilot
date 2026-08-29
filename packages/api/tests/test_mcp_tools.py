# This project was developed with assistance from AI tools.
"""Unit tests for MCP risk assessment tool functions.

Tests the computation logic directly (no MCP transport).
"""

import json

from src.mcp_server import (
    assess_asset_sufficiency,
    assess_income_stability,
    calculate_dti,
    calculate_ltv,
    evaluate_credit_risk,
    generate_risk_recommendation,
)


class TestCalculateDti:
    """DTI computation and risk rating."""

    def test_low_dti(self):
        """DTI < 36% rated Low."""
        result = json.loads(calculate_dti(monthly_income=10000, monthly_debts=2000))
        assert result["value"] == 20.0
        assert result["rating"] == "低"

    def test_medium_dti(self):
        """DTI 36-43% rated Medium."""
        result = json.loads(calculate_dti(monthly_income=10000, monthly_debts=4000))
        assert result["value"] == 40.0
        assert result["rating"] == "中"

    def test_high_dti(self):
        """DTI > 43% rated High."""
        result = json.loads(calculate_dti(monthly_income=10000, monthly_debts=5100))
        assert result["value"] == 51.0
        assert result["rating"] == "高"

    def test_zero_income(self):
        """Zero income returns null with warning."""
        result = json.loads(calculate_dti(monthly_income=0, monthly_debts=2000))
        assert result["value"] is None
        assert result["rating"] is None
        assert "warning" in result

    def test_boundary_at_36(self):
        """DTI exactly 36% is Medium (not Low)."""
        result = json.loads(calculate_dti(monthly_income=10000, monthly_debts=3600))
        assert result["value"] == 36.0
        assert result["rating"] == "低"

    def test_boundary_at_43(self):
        """DTI exactly 43% is Medium (not High)."""
        result = json.loads(calculate_dti(monthly_income=10000, monthly_debts=4300))
        assert result["value"] == 43.0
        assert result["rating"] == "中"


class TestCalculateLtv:
    """LTV computation and risk rating."""

    def test_low_ltv(self):
        """LTV < 60% rated Low."""
        result = json.loads(calculate_ltv(loan_amount=200000, property_value=500000))
        assert result["value"] == 40.0
        assert result["rating"] == "低"

    def test_medium_ltv(self):
        """LTV 60-80% rated Medium."""
        result = json.loads(calculate_ltv(loan_amount=350000, property_value=500000))
        assert result["value"] == 70.0
        assert result["rating"] == "中"

    def test_high_ltv_with_pmi_note(self):
        """LTV > 80% rated High with PMI note."""
        result = json.loads(calculate_ltv(loan_amount=450000, property_value=500000))
        assert result["value"] == 90.0
        assert result["rating"] == "高"
        assert "全国与成都政策" in result["note"]

    def test_zero_property_value(self):
        """Zero property value returns null with warning."""
        result = json.loads(calculate_ltv(loan_amount=350000, property_value=0))
        assert result["value"] is None
        assert "warning" in result


class TestEvaluateCreditRisk:
    """Credit score risk evaluation."""

    def test_low_risk(self):
        """Score > 680 rated Low."""
        result = json.loads(evaluate_credit_risk(credit_score=750, source="bureau_hard_pull"))
        assert result["rating"] == "低"
        assert result["source"] == "bureau_hard_pull"

    def test_medium_risk(self):
        """Score 620-680 rated Medium."""
        result = json.loads(evaluate_credit_risk(credit_score=650))
        assert result["rating"] == "中"

    def test_high_risk(self):
        """Score < 620 rated High."""
        result = json.loads(evaluate_credit_risk(credit_score=580))
        assert result["rating"] == "高"

    def test_zero_score(self):
        """Zero score returns null with warning."""
        result = json.loads(evaluate_credit_risk(credit_score=0))
        assert result["value"] is None
        assert "warning" in result


class TestAssessIncomeStability:
    """Income stability from employment statuses."""

    def test_w2_employee_low(self):
        """W2 employee rated Low."""
        result = json.loads(assess_income_stability(employment_statuses=["w2_employee"]))
        assert result["rating"] == "低"

    def test_unemployed_high(self):
        """Unemployed rated High."""
        result = json.loads(assess_income_stability(employment_statuses=["unemployed"]))
        assert result["rating"] == "高"

    def test_worst_case_across_borrowers(self):
        """Multiple borrowers: worst rating wins."""
        result = json.loads(
            assess_income_stability(employment_statuses=["w2_employee", "unemployed"])
        )
        assert result["rating"] == "高"

    def test_empty_statuses(self):
        """No statuses returns null with warning."""
        result = json.loads(assess_income_stability(employment_statuses=[]))
        assert result["value"] is None
        assert "warning" in result


class TestAssessAssetSufficiency:
    """Asset sufficiency ratio and risk rating."""

    def test_low_risk(self):
        """Assets > 20% of loan rated Low."""
        result = json.loads(assess_asset_sufficiency(total_assets=100000, loan_amount=300000))
        assert result["value"] == 33.3
        assert result["rating"] == "低"

    def test_high_risk(self):
        """Assets < 10% of loan rated High."""
        result = json.loads(assess_asset_sufficiency(total_assets=20000, loan_amount=300000))
        assert result["value"] == 6.7
        assert result["rating"] == "高"

    def test_zero_assets(self):
        """Zero assets returns null with warning."""
        result = json.loads(assess_asset_sufficiency(total_assets=0, loan_amount=300000))
        assert result["value"] is None
        assert "warning" in result


class TestGenerateRiskRecommendation:
    """Recommendation generation from aggregated risk factors."""

    def _base_params(self):
        return {
            "dti_value": 30.0,
            "dti_rating": "低",
            "ltv_value": 70.0,
            "ltv_rating": "中",
            "credit_score": 720,
            "credit_rating": "低",
            "income_stability_rating": "低",
            "income_stability_value": "w2_employee",
            "asset_sufficiency_value": 33.3,
            "asset_sufficiency_rating": "低",
            "employment_statuses": ["w2_employee"],
            "has_financials": True,
            "doc_count": 3,
        }

    def test_approve(self):
        """All low risk -> Approve."""
        result = json.loads(generate_risk_recommendation(**self._base_params()))
        assert result["recommendation"] == "可提交人工决策"
        assert result["overall_risk"] in ("低", "中")

    def test_deny_extreme_dti(self):
        """DTI > 55% triggers Deny."""
        params = self._base_params()
        params["dti_value"] = 60.0
        params["dti_rating"] = "高"
        result = json.loads(generate_risk_recommendation(**params))
        assert result["recommendation"] == "需重点人工复核"
        assert any("55%" in r for r in result["rationale"])

    def test_deny_low_credit(self):
        """Credit < 580 triggers Deny."""
        params = self._base_params()
        params["credit_score"] = 550
        params["credit_rating"] = "高"
        result = json.loads(generate_risk_recommendation(**params))
        assert result["recommendation"] == "需重点人工复核"
        assert any("600" in r for r in result["rationale"])

    def test_suspend_missing_financials(self):
        """Missing financials triggers Suspend."""
        params = self._base_params()
        params["has_financials"] = False
        result = json.loads(generate_risk_recommendation(**params))
        assert result["recommendation"] == "需补充材料"

    def test_conditions_high_ltv(self):
        """LTV > 80% triggers PMI condition."""
        params = self._base_params()
        params["ltv_value"] = 90.0
        params["ltv_rating"] = "高"
        result = json.loads(generate_risk_recommendation(**params))
        assert result["recommendation"] == "需重点人工复核"
        assert any("全国及成都政策" in c for c in result["conditions"])

    def test_compensating_factors(self):
        """Strong credit + high DTI triggers compensating factor."""
        params = self._base_params()
        params["dti_value"] = 45.0
        params["dti_rating"] = "高"
        params["credit_score"] = 760
        params["credit_rating"] = "低"
        result = json.loads(generate_risk_recommendation(**params))
        assert any("模拟征信评分较高" in f for f in result["compensating_factors"])

    def test_ml_approval_adds_compensating_factor(self):
        """ML model approval adds compensating factor."""
        params = self._base_params()
        params["predictive_model_result"] = "Loan approved"
        result = json.loads(generate_risk_recommendation(**params))
        assert any("外部预测模型结果" in f for f in result["compensating_factors"])

    def test_ml_rejection_adds_warning(self):
        """ML model rejection adds warning."""
        params = self._base_params()
        params["predictive_model_result"] = "Loan rejected"
        result = json.loads(generate_risk_recommendation(**params))
        assert any("外部预测模型提示风险升高" in w for w in result["warnings"])

    def test_ml_rejection_escalates_approve_to_conditions(self):
        """ML rejection escalates clean Approve to Approve with Conditions."""
        params = self._base_params()
        params["predictive_model_result"] = "Loan rejected"
        result = json.loads(generate_risk_recommendation(**params))
        assert result["recommendation"] == "需重点人工复核"
        assert any("预测模型" in c for c in result["conditions"])

    def test_ml_none_has_no_effect(self):
        """No ML result (None) does not affect recommendation."""
        params = self._base_params()
        params["predictive_model_result"] = None
        result = json.loads(generate_risk_recommendation(**params))
        assert result["recommendation"] == "可提交人工决策"
        assert not any("预测模型" in f for f in result["compensating_factors"])
        assert not any("预测模型" in w for w in result["warnings"])
