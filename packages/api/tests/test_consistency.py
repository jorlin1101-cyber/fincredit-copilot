# This project was developed with assistance from AI tools.
"""Tests for deterministic P0 cross-document consistency checks."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from db.enums import DocumentStatus, DocumentType, UserRole
from db.models import ApplicationFinancials, Document, DocumentExtraction

from src.schemas.auth import DataScope, UserContext
from src.schemas.consistency import ConsistencyEvidence
from src.services.consistency import (
    RULE_VERSIONS,
    evaluate_income_consistency,
    evaluate_name_consistency,
    run_consistency_check,
)


def _user():
    return UserContext(
        user_id="reviewer-1",
        role=UserRole.LOAN_OFFICER,
        email="reviewer@example.test",
        name="审核员",
        data_scope=DataScope(full_pipeline=True),
    )


def _evidence(
    value: str,
    *,
    normalized: str,
    document_id: int,
    document_type: DocumentType,
    field_name: str,
):
    return ConsistencyEvidence(
        source_kind="document",
        document_id=document_id,
        document_type=document_type,
        field_name=field_name,
        value=value,
        normalized_value=normalized,
        source_page=1,
        evidence_text=value,
    )


def test_name_rule_reports_exact_normalized_mismatch():
    evidence = [
        _evidence(
            "张晨",
            normalized="张晨",
            document_id=1,
            document_type=DocumentType.ID_CARD,
            field_name="full_name",
        ),
        _evidence(
            "张辰",
            normalized="张辰",
            document_id=2,
            document_type=DocumentType.INCOME_CERTIFICATE,
            field_name="employee_name",
        ),
    ]
    issues = evaluate_name_consistency(evidence)
    assert len(issues) == 1
    assert issues[0].issue_type == "name_mismatch"
    assert issues[0].rule_version == RULE_VERSIONS["name"]
    assert issues[0].left.source_page == 1


def test_name_rule_passes_after_human_correction():
    evidence = [
        _evidence(
            "张晨",
            normalized="张晨",
            document_id=1,
            document_type=DocumentType.ID_CARD,
            field_name="full_name",
        ),
        _evidence(
            "张晨",
            normalized="张晨",
            document_id=2,
            document_type=DocumentType.INCOME_CERTIFICATE,
            field_name="employee_name",
        ),
    ]
    assert evaluate_name_consistency(evidence) == []


def test_income_rule_uses_configured_relative_threshold():
    evidence = [
        ConsistencyEvidence(
            source_kind="application",
            field_name="gross_monthly_income",
            value="20000.00",
            normalized_value="20000.00",
        ),
        _evidence(
            "15000元",
            normalized="15000.00",
            document_id=3,
            document_type=DocumentType.BANK_STATEMENT,
            field_name="salary_credit_monthly_average",
        ),
    ]
    issues = evaluate_income_consistency(evidence, threshold=0.15)
    assert len(issues) == 1
    assert issues[0].difference_ratio == 0.25
    assert issues[0].threshold == 0.15


def test_income_rule_allows_difference_within_threshold():
    evidence = [
        ConsistencyEvidence(
            source_kind="application",
            field_name="gross_monthly_income",
            value="20000.00",
            normalized_value="20000.00",
        ),
        _evidence(
            "18500元",
            normalized="18500.00",
            document_id=3,
            document_type=DocumentType.BANK_STATEMENT,
            field_name="salary_credit_monthly_average",
        ),
    ]
    assert evaluate_income_consistency(evidence, threshold=0.15) == []


@pytest.mark.asyncio
async def test_run_check_returns_source_grounded_name_and_income_issues():
    id_doc = Document(
        id=1,
        application_id=99,
        doc_type=DocumentType.ID_CARD,
        status=DocumentStatus.PROCESSING_COMPLETE,
    )
    income_doc = Document(
        id=2,
        application_id=99,
        doc_type=DocumentType.INCOME_CERTIFICATE,
        status=DocumentStatus.PROCESSING_COMPLETE,
    )
    bank_doc = Document(
        id=3,
        application_id=99,
        doc_type=DocumentType.BANK_STATEMENT,
        status=DocumentStatus.PROCESSING_COMPLETE,
    )
    rows = [
        (
            DocumentExtraction(
                id=11,
                document_id=1,
                field_name="full_name",
                field_value="张晨",
                normalized_value="张晨",
                confidence=0.99,
                source_page=1,
                evidence_text="姓名 张晨",
            ),
            id_doc,
        ),
        (
            DocumentExtraction(
                id=12,
                document_id=2,
                field_name="employee_name",
                field_value="张辰",
                normalized_value="张辰",
                confidence=0.98,
                source_page=1,
                evidence_text="员工张辰",
            ),
            income_doc,
        ),
        (
            DocumentExtraction(
                id=13,
                document_id=2,
                field_name="monthly_gross_income",
                field_value="20000元",
                normalized_value="20000.00",
                confidence=0.97,
                source_page=1,
                evidence_text="月收入20000元",
            ),
            income_doc,
        ),
        (
            DocumentExtraction(
                id=14,
                document_id=3,
                field_name="salary_credit_monthly_average",
                field_value="15000元",
                normalized_value="15000.00",
                confidence=0.96,
                source_page=2,
                evidence_text="工资入账均值15000元",
            ),
            bank_doc,
        ),
    ]
    financial = ApplicationFinancials(
        id=1,
        application_id=99,
        gross_monthly_income=Decimal("20000.00"),
    )

    financial_result = MagicMock()
    financial_result.scalars.return_value.all.return_value = [financial]
    extraction_result = MagicMock()
    extraction_result.all.return_value = rows
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[financial_result, extraction_result])

    with (
        patch("src.services.consistency.get_application", new_callable=AsyncMock) as get_app,
        patch(
            "src.services.consistency.write_audit_event",
            new_callable=AsyncMock,
        ) as audit,
    ):
        get_app.return_value = MagicMock(id=99)
        result = await run_consistency_check(session, _user(), 99)

    assert result is not None
    assert result.status == "issues_found"
    assert result.checks_performed == ["name", "monthly_income"]
    assert {issue.issue_type for issue in result.issues} == {
        "name_mismatch",
        "income_mismatch",
    }
    assert any(issue.right.source_page == 2 for issue in result.issues)
    audit.assert_awaited_once()
    session.commit.assert_awaited_once()
