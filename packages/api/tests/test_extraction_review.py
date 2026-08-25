# This project was developed with assistance from AI tools.
"""Tests for human extraction correction and audit evidence."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from db import get_db
from db.enums import DocumentType, ExtractionMethod, UserRole
from db.models import Document, DocumentExtraction, ExtractionCorrection
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.middleware.auth import get_current_user
from src.routes.documents import router
from src.schemas.auth import DataScope, UserContext
from src.services.extraction_review import correct_extraction


def _user():
    return UserContext(
        user_id="reviewer-1",
        role=UserRole.LOAN_OFFICER,
        email="reviewer@example.test",
        name="审核员",
        data_scope=DataScope(full_pipeline=True),
    )


@pytest.mark.asyncio
async def test_correction_preserves_before_after_and_marks_manual():
    document = Document(id=3, application_id=99, doc_type=DocumentType.INCOME_CERTIFICATE)
    extraction = DocumentExtraction(
        id=7,
        document_id=3,
        field_name="monthly_gross_income",
        field_value="人民币壹万伍仟元",
        normalized_value="15000.00",
        confidence=0.61,
        source_page=1,
        evidence_text="月收入人民币贰万元整",
    )
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = extraction
    session = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock(return_value=query_result)

    with (
        patch(
            "src.services.extraction_review.document_service.get_document",
            new_callable=AsyncMock,
            return_value=document,
        ),
        patch(
            "src.services.extraction_review.write_audit_event",
            new_callable=AsyncMock,
        ) as audit,
    ):
        result = await correct_extraction(
            session,
            _user(),
            application_id=99,
            document_id=3,
            extraction_id=7,
            new_value="人民币贰万元整",
            reason="对照收入证明原件人工修正",
        )

    assert result is not None
    correction, updated = result
    assert isinstance(correction, ExtractionCorrection)
    assert correction.old_value == "人民币壹万伍仟元"
    assert correction.new_value == "人民币贰万元整"
    assert correction.old_normalized_value == "15000.00"
    assert correction.new_normalized_value == "20000.00"
    assert correction.corrected_by == "reviewer-1"
    assert updated.field_value == "人民币贰万元整"
    assert updated.normalized_value == "20000.00"
    assert updated.extraction_method == ExtractionMethod.MANUAL
    assert updated.confidence == 1.0
    audit.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_identical_correction_is_rejected():
    document = Document(id=3, application_id=99, doc_type=DocumentType.ID_CARD)
    extraction = DocumentExtraction(
        id=7,
        document_id=3,
        field_name="full_name",
        field_value="张晨",
        normalized_value="张晨",
    )
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = extraction
    session = AsyncMock()
    session.execute = AsyncMock(return_value=query_result)

    with patch(
        "src.services.extraction_review.document_service.get_document",
        new_callable=AsyncMock,
        return_value=document,
    ):
        with pytest.raises(ValueError, match="identical"):
            await correct_extraction(
                session,
                _user(),
                application_id=99,
                document_id=3,
                extraction_id=7,
                new_value="张晨",
                reason="重复提交",
            )


def test_correction_endpoint_returns_before_after_and_current_field():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    user = _user()

    async def fake_user():
        return user

    async def fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_db

    extraction = DocumentExtraction(
        id=7,
        document_id=3,
        field_name="monthly_gross_income",
        field_value="人民币贰万元整",
        normalized_value="20000.00",
        confidence=1.0,
        source_page=1,
        evidence_text="月收入人民币贰万元整",
        extraction_method=ExtractionMethod.MANUAL,
    )
    correction = ExtractionCorrection(
        id=8,
        extraction_id=7,
        old_value="人民币壹万伍仟元",
        new_value="人民币贰万元整",
        old_normalized_value="15000.00",
        new_normalized_value="20000.00",
        reason="对照原件修正",
        corrected_by="reviewer-1",
        corrected_at=datetime.now(UTC),
    )
    with patch(
        "src.routes.documents.correct_extraction",
        new_callable=AsyncMock,
        return_value=(correction, extraction),
    ):
        response = TestClient(app).patch(
            "/api/applications/99/documents/3/extractions/7",
            json={"new_value": "人民币贰万元整", "reason": "对照原件修正"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["old_normalized_value"] == "15000.00"
    assert payload["new_normalized_value"] == "20000.00"
    assert payload["extraction"]["extraction_method"] == "manual"
