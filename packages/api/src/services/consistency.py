# This project was developed with assistance from AI tools.
"""Deterministic cross-document checks for the two P0 anomaly types."""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from itertools import combinations

from db import ApplicationFinancials, Document, DocumentExtraction
from db.enums import DocumentStatus, DocumentType, ExtractionMethod
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..schemas.auth import UserContext
from ..schemas.consistency import (
    ConsistencyCheckResponse,
    ConsistencyEvidence,
    ConsistencyIssue,
)
from .application import get_application
from .audit import write_audit_event
from .extraction_normalization import normalize_amount, normalize_name

RULE_VERSIONS = {
    "name": "name-exact-v1",
    "monthly_income": "income-relative-v1",
}

_NAME_FIELDS = {
    DocumentType.ID_CARD: "full_name",
    DocumentType.INCOME_CERTIFICATE: "employee_name",
    DocumentType.BANK_STATEMENT: "account_holder_name",
}
_INCOME_FIELDS = {
    DocumentType.INCOME_CERTIFICATE: {
        "monthly_gross_income",
        "annual_gross_income",
    },
    DocumentType.BANK_STATEMENT: {"salary_credit_monthly_average"},
}
_USABLE_STATUSES = {
    DocumentStatus.PROCESSING_COMPLETE,
    DocumentStatus.PENDING_REVIEW,
    DocumentStatus.ACCEPTED,
}


def evaluate_name_consistency(evidence: list[ConsistencyEvidence]) -> list[ConsistencyIssue]:
    """Compare already-normalized names with exact deterministic equality."""
    issues: list[ConsistencyIssue] = []
    for left, right in combinations(evidence, 2):
        if left.normalized_value == right.normalized_value:
            continue
        issues.append(
            ConsistencyIssue(
                issue_type="name_mismatch",
                field_name="name",
                left=left,
                right=right,
                threshold=0.0,
                rule_version=RULE_VERSIONS["name"],
                recommendation="请人工核对姓名原文及身份证件，确认是否为录入或抽取错误。",
            )
        )
    return issues


def _as_decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def evaluate_income_consistency(
    evidence: list[ConsistencyEvidence],
    *,
    threshold: float,
) -> list[ConsistencyIssue]:
    """Compare declared, certified and statement monthly income pairwise."""
    issues: list[ConsistencyIssue] = []
    for left, right in combinations(evidence, 2):
        left_value = _as_decimal(left.normalized_value)
        right_value = _as_decimal(right.normalized_value)
        if left_value is None or right_value is None:
            continue
        denominator = max(abs(left_value), abs(right_value), Decimal("1"))
        difference = abs(left_value - right_value) / denominator
        if difference <= Decimal(str(threshold)):
            continue
        issues.append(
            ConsistencyIssue(
                issue_type="income_mismatch",
                field_name="monthly_income",
                left=left,
                right=right,
                difference_ratio=round(float(difference), 4),
                threshold=threshold,
                rule_version=RULE_VERSIONS["monthly_income"],
                recommendation=(
                    "请核对申报月收入、收入证明与近三个月工资入账均值，必要时要求补充说明或材料。"
                ),
            )
        )
    return issues


def _extraction_score(extraction: DocumentExtraction) -> tuple[int, float, int]:
    method = extraction.extraction_method
    is_manual = method == ExtractionMethod.MANUAL or method == ExtractionMethod.MANUAL.value
    return (int(is_manual), float(extraction.confidence or 0), int(extraction.id or 0))


def _best_extractions(rows) -> list[tuple[DocumentExtraction, Document]]:
    """Choose one current value per document/field, preferring human corrections."""
    best: dict[tuple[int, str], tuple[DocumentExtraction, Document]] = {}
    for extraction, document in rows:
        key = (document.id, extraction.field_name)
        current = best.get(key)
        if current is None or _extraction_score(extraction) > _extraction_score(current[0]):
            best[key] = (extraction, document)
    return list(best.values())


def _document_evidence(
    extraction: DocumentExtraction,
    document: Document,
    *,
    normalized_value: str,
) -> ConsistencyEvidence:
    return ConsistencyEvidence(
        source_kind="document",
        document_id=document.id,
        document_type=document.doc_type,
        field_name=extraction.field_name,
        value=extraction.field_value or "",
        normalized_value=normalized_value,
        source_page=extraction.source_page,
        evidence_text=extraction.evidence_text,
    )


async def run_consistency_check(
    session: AsyncSession,
    user: UserContext,
    application_id: int,
) -> ConsistencyCheckResponse | None:
    """Load source evidence, run fixed rules, and append an audit event."""
    application = await get_application(session, user, application_id)
    if application is None:
        return None

    financial_result = await session.execute(
        select(ApplicationFinancials).where(ApplicationFinancials.application_id == application_id)
    )
    financials = list(financial_result.scalars().all())

    extraction_result = await session.execute(
        select(DocumentExtraction, Document)
        .join(Document, Document.id == DocumentExtraction.document_id)
        .where(
            Document.application_id == application_id,
            Document.doc_type.in_(list(_NAME_FIELDS) + list(_INCOME_FIELDS)),
            Document.status.in_(_USABLE_STATUSES),
        )
    )
    rows = _best_extractions(extraction_result.all())

    name_evidence: list[ConsistencyEvidence] = []
    income_evidence: list[ConsistencyEvidence] = []
    monthly_income_documents: set[int] = set()
    annual_income_candidates: list[tuple[DocumentExtraction, Document]] = []

    for extraction, document in rows:
        if extraction.field_name == _NAME_FIELDS.get(document.doc_type):
            normalized = extraction.normalized_value or normalize_name(extraction.field_value or "")
            if normalized:
                name_evidence.append(
                    _document_evidence(extraction, document, normalized_value=normalized)
                )

        income_fields = _INCOME_FIELDS.get(document.doc_type, set())
        if extraction.field_name not in income_fields:
            continue
        if extraction.field_name == "annual_gross_income":
            annual_income_candidates.append((extraction, document))
            continue
        normalized = extraction.normalized_value or normalize_amount(extraction.field_value or "")
        if normalized:
            income_evidence.append(
                _document_evidence(extraction, document, normalized_value=normalized)
            )
            monthly_income_documents.add(document.id)

    for extraction, document in annual_income_candidates:
        if document.id in monthly_income_documents:
            continue
        annual = _as_decimal(
            extraction.normalized_value or normalize_amount(extraction.field_value or "") or ""
        )
        if annual is not None:
            income_evidence.append(
                _document_evidence(
                    extraction,
                    document,
                    normalized_value=f"{annual / Decimal('12'):.2f}",
                )
            )

    for financial in financials:
        if financial.gross_monthly_income is None:
            continue
        normalized = f"{Decimal(financial.gross_monthly_income):.2f}"
        income_evidence.append(
            ConsistencyEvidence(
                source_kind="application",
                field_name="gross_monthly_income",
                value=normalized,
                normalized_value=normalized,
                evidence_text="申请表申报月收入",
            )
        )

    checks_performed = []
    issues: list[ConsistencyIssue] = []
    warnings: list[str] = []
    if len(name_evidence) >= 2:
        checks_performed.append("name")
        issues.extend(evaluate_name_consistency(name_evidence))
    else:
        warnings.append("姓名证据不足：至少需要两类材料中的姓名字段。")

    if len(income_evidence) >= 2:
        checks_performed.append("monthly_income")
        issues.extend(
            evaluate_income_consistency(
                income_evidence,
                threshold=settings.INCOME_MISMATCH_THRESHOLD,
            )
        )
    else:
        warnings.append("收入证据不足：至少需要申报、收入证明或流水中的两项。")

    status = "issues_found" if issues else ("passed" if checks_performed else "insufficient_data")
    response = ConsistencyCheckResponse(
        application_id=application_id,
        status=status,
        checked_at=datetime.now(UTC),
        checks_performed=checks_performed,
        issues=issues,
        warnings=warnings,
        rule_versions=RULE_VERSIONS,
    )
    await write_audit_event(
        session,
        event_type="document_consistency_checked",
        user_id=user.user_id,
        user_role=user.role.value,
        application_id=application_id,
        event_data=response.model_dump(mode="json"),
    )
    await session.commit()
    return response
