# This project was developed with assistance from AI tools.
"""Tests for Chinese P0 document and policy metadata schemas."""

import json
from datetime import date
from pathlib import Path

import pytest
from db.enums import DocumentType, ExtractionMethod, PolicyJurisdiction, PolicySourceType
from pydantic import ValidationError

from src.schemas.chinese_document import (
    BankStatementSchema,
    EvidenceField,
    IdentityCardSchema,
    IncomeCertificateSchema,
)
from src.schemas.policy import PolicyMetadata

_SAMPLE_ROOT = Path(__file__).resolve().parents[3] / "data" / "schema-samples"


@pytest.mark.parametrize(
    ("filename", "schema"),
    [
        ("id-card.json", IdentityCardSchema),
        ("income-certificate.json", IncomeCertificateSchema),
        ("bank-statement.json", BankStatementSchema),
    ],
)
def test_sample_json_matches_schema(filename, schema):
    payload = json.loads((_SAMPLE_ROOT / filename).read_text(encoding="utf-8"))
    parsed = schema.model_validate(payload)
    assert parsed.document_type == payload["document_type"]


def test_p0_document_types_are_available():
    assert DocumentType.ID_CARD.value == "id_card"
    assert DocumentType.INCOME_CERTIFICATE.value == "income_certificate"
    assert DocumentType.BANK_STATEMENT.value == "bank_statement"


def test_evidence_field_rejects_invalid_confidence_and_page():
    with pytest.raises(ValidationError):
        EvidenceField(
            value="20,000元",
            confidence=1.2,
            source_page=0,
            evidence_text="月收入20,000元",
            extraction_method=ExtractionMethod.TEXT_LAYER,
        )


def test_official_policy_requires_source_url():
    with pytest.raises(ValidationError, match="requires source_url"):
        PolicyMetadata(
            title="政策样例",
            issuer="监管机构",
            jurisdiction=PolicyJurisdiction.NATIONAL,
            source_type=PolicySourceType.OFFICIAL,
        )


def test_policy_metadata_sample_matches_schema():
    payload = json.loads((_SAMPLE_ROOT / "policy-internal-demo.json").read_text(encoding="utf-8"))
    parsed = PolicyMetadata.model_validate(payload)
    assert parsed.jurisdiction == PolicyJurisdiction.INTERNAL_DEMO
    assert parsed.source_type == PolicySourceType.INTERNAL_DEMO


def test_policy_rejects_invalid_date_range():
    with pytest.raises(ValidationError, match="must not be earlier"):
        PolicyMetadata(
            title="政策样例",
            issuer="监管机构",
            source_url="https://example.gov.cn/policy",
            jurisdiction=PolicyJurisdiction.CHENGDU,
            source_type=PolicySourceType.OFFICIAL,
            effective_date=date(2026, 8, 2),
            expires_at=date(2026, 8, 1),
        )


def test_internal_demo_policy_must_be_explicitly_labelled():
    with pytest.raises(ValidationError, match="internal_demo jurisdiction"):
        PolicyMetadata(
            title="融安内部演示规则",
            issuer="融安住房金融（虚构）",
            jurisdiction=PolicyJurisdiction.NATIONAL,
            source_type=PolicySourceType.INTERNAL_DEMO,
        )
