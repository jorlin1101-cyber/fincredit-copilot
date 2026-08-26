# This project was developed with assistance from AI tools.
"""Tests for public API endpoints (products + affordability calculator)."""


def test_products_endpoint(client):
    response = client.get("/api/public/products")
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_affordability_happy_path(client):
    """Chinese calculator applies the national down-payment floor."""
    response = client.post(
        "/api/public/calculate-affordability",
        json={
            "gross_annual_income": 240000,
            "monthly_debts": 2000,
            "monthly_property_fee": 300,
            "down_payment": 300000,
            "interest_rate": 3.5,
            "loan_term_years": 30,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["max_loan_amount"] > 0
    assert data["estimated_monthly_payment"] > 0
    assert data["estimated_purchase_price"] > data["max_loan_amount"]
    assert data["dti_ratio"] > 0
    assert data["dti_warning"] is None
    assert data["estimated_purchase_price"] == 2000000
    assert data["max_loan_amount"] == 1700000
    assert data["ltv_ratio"] == 85
    assert data["down_payment_ratio"] == 15
    assert data["binding_constraint"] == "down_payment"
    assert data["minimum_down_payment_ratio"] == 15


def test_affordability_debts_exceed_capacity(client):
    """Existing debt above the total-debt cap leaves no new repayment capacity."""
    response = client.post(
        "/api/public/calculate-affordability",
        json={
            "gross_annual_income": 240000,
            "monthly_debts": 12000,
            "monthly_property_fee": 300,
            "down_payment": 300000,
        },
    )
    data = response.json()
    assert data["max_loan_amount"] == 0
    assert data["estimated_monthly_payment"] == 0
    assert data["dti_warning"] is not None


def test_affordability_repayment_capacity_can_be_binding(client):
    """A large down payment does not bypass repayment-capacity constraints."""
    response = client.post(
        "/api/public/calculate-affordability",
        json={
            "gross_annual_income": 240000,
            "monthly_debts": 2000,
            "monthly_property_fee": 300,
            "down_payment": 1000000,
            "interest_rate": 3.5,
        },
    )
    data = response.json()
    assert data["binding_constraint"] == "repayment_capacity"
    assert data["housing_expense_ratio"] <= 50
    assert data["dti_ratio"] <= 55
    assert data["pmi_warning"] is None


def test_affordability_requires_down_payment(client):
    response = client.post(
        "/api/public/calculate-affordability",
        json={
            "gross_annual_income": 240000,
            "monthly_debts": 0,
            "down_payment": 0,
        },
    )
    data = response.json()
    assert data["estimated_purchase_price"] == 0
    assert data["dti_warning"] is not None


def test_affordability_rejects_negative_income(client):
    """Negative income should fail validation."""
    response = client.post(
        "/api/public/calculate-affordability",
        json={
            "gross_annual_income": -50000,
            "monthly_debts": 500,
            "down_payment": 10000,
        },
    )
    assert response.status_code == 422
