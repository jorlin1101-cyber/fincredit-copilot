# This project was developed with assistance from AI tools.
"""Tests for deterministic DTI/LTV and mandatory human review."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from db import RiskAssessmentRecord
from db.enums import DocumentStatus, DocumentType, UserRole

from src.schemas.auth import DataScope, UserContext
from src.services.deterministic_assessment import (
    build_document_gate,
    calculate_dti,
    calculate_ltv,
    derive_suggestion,
    run_deterministic_assessment,
)


def _document(doc_type, status=DocumentStatus.ACCEPTED, quality_flags=None):
    return SimpleNamespace(doc_type=doc_type, status=status, quality_flags=quality_flags)


def _user():
    return UserContext(
        user_id="underwriter-1",
        role=UserRole.UNDERWRITER,
        email="underwriter@example.test",
        name="审批员",
        data_scope=DataScope(full_pipeline=True),
    )


def test_dti_includes_existing_debt_and_proposed_housing_payment():
    metric = calculate_dti(10_000, 1_000, 2_500)
    assert metric.value == 35.0
    assert metric.rating == "Low"
    assert metric.inputs["proposed_monthly_payment"] == 2_500


def test_dti_missing_income_fails_closed():
    metric = calculate_dti(0, 1_000, 2_500)
    assert metric.value is None
    assert metric.rating is None


def test_ltv_is_deterministic_and_uses_synthetic_review_band():
    metric = calculate_ltv(800_000, 1_000_000)
    assert metric.value == 80.0
    assert metric.rating == "Medium"
    assert "贷款金额" in metric.formula


def test_document_gate_requires_three_p0_chinese_documents():
    gate = build_document_gate(
        [
            _document(DocumentType.ID_CARD),
            _document(DocumentType.INCOME_CERTIFICATE, DocumentStatus.PENDING_REVIEW),
        ]
    )
    assert not gate.is_complete
    assert gate.missing == ["银行流水"]
    assert gate.pending_human_review == ["收入证明"]


def test_suggestion_never_returns_approve_or_deny():
    dti = calculate_dti(10_000, 1_000, 2_500)
    ltv = calculate_ltv(700_000, 1_000_000)
    documents = build_document_gate(
        [
            _document(DocumentType.ID_CARD),
            _document(DocumentType.INCOME_CERTIFICATE),
            _document(DocumentType.BANK_STATEMENT),
        ]
    )
    suggestion, rationale = derive_suggestion(
        dti,
        ltv,
        documents,
        "passed",
        proposed_monthly_payment=2_500,
    )
    assert suggestion == "READY_FOR_HUMAN_DECISION"
    assert "APPROVE" not in suggestion
    assert "DENY" not in suggestion
    assert any("最终决策" in item for item in rationale)


@pytest.mark.asyncio
async def test_full_assessment_persists_inputs_results_trace_and_human_boundary(monkeypatch):
    session = AsyncMock()
    stored = []
    session.add = stored.append
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    document_result = MagicMock()
    document_result.scalars.return_value.all.return_value = [
        _document(DocumentType.ID_CARD),
        _document(DocumentType.INCOME_CERTIFICATE),
        _document(DocumentType.BANK_STATEMENT),
    ]
    session.execute = AsyncMock(return_value=document_result)

    consistency = MagicMock()
    consistency.status = "passed"
    consistency.issues = []
    consistency.model_dump.return_value = {"status": "passed", "issues": []}

    import src.services.deterministic_assessment as mod

    monkeypatch.setattr(
        mod,
        "get_application",
        AsyncMock(return_value=SimpleNamespace(loan_amount=700_000, property_value=1_000_000)),
    )
    monkeypatch.setattr(
        mod,
        "get_financials",
        AsyncMock(return_value=[SimpleNamespace(gross_monthly_income=20_000, monthly_debts=2_000)]),
    )
    monkeypatch.setattr(mod, "run_consistency_check", AsyncMock(return_value=consistency))
    audit = AsyncMock()
    monkeypatch.setattr(mod, "write_audit_event", audit)

    result = await run_deterministic_assessment(
        session,
        _user(),
        101,
        proposed_monthly_payment=5_000,
        trace_id="trace-d9-001",
    )

    assert result is not None
    assert result.dti.value == 35.0
    assert result.ltv.value == 70.0
    assert result.human_review_required is True
    assert result.suggestion == "READY_FOR_HUMAN_DECISION"
    record = next(item for item in stored if isinstance(item, RiskAssessmentRecord))
    assert record.trace_id == "trace-d9-001"
    assert record.human_review_required is True
    assert record.calculation_inputs["dti"]["proposed_monthly_payment"] == 5_000
    audit.assert_awaited_once()
    session.commit.assert_awaited_once()
