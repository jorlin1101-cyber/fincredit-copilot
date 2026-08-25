# This project was developed with assistance from AI tools.
"""Human review operations for extracted document fields."""

from db import DocumentExtraction, ExtractionCorrection
from db.enums import ExtractionMethod
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..schemas.auth import UserContext
from . import document as document_service
from .audit import write_audit_event
from .extraction_normalization import normalize_extracted_value


async def correct_extraction(
    session: AsyncSession,
    user: UserContext,
    *,
    application_id: int,
    document_id: int,
    extraction_id: int,
    new_value: str,
    reason: str,
) -> tuple[ExtractionCorrection, DocumentExtraction] | None:
    """Correct a field while preserving an append-only before/after record."""
    document = await document_service.get_document(session, user, document_id)
    if document is None or document.application_id != application_id:
        return None

    result = await session.execute(
        select(DocumentExtraction).where(
            DocumentExtraction.id == extraction_id,
            DocumentExtraction.document_id == document_id,
        )
    )
    extraction = result.scalar_one_or_none()
    if extraction is None:
        return None

    clean_value = new_value.strip()
    new_normalized = normalize_extracted_value(extraction.field_name, clean_value)
    if clean_value == extraction.field_value and new_normalized == extraction.normalized_value:
        raise ValueError("new value is identical to the current extracted value")

    correction = ExtractionCorrection(
        extraction_id=extraction.id,
        old_value=extraction.field_value,
        new_value=clean_value,
        old_normalized_value=extraction.normalized_value,
        new_normalized_value=new_normalized,
        reason=reason.strip(),
        corrected_by=user.user_id,
    )
    correction.extraction = extraction
    session.add(correction)

    extraction.field_value = clean_value
    extraction.normalized_value = new_normalized
    extraction.extraction_method = ExtractionMethod.MANUAL
    extraction.confidence = 1.0

    await session.flush()
    await write_audit_event(
        session,
        event_type="document_extraction_corrected",
        user_id=user.user_id,
        user_role=user.role.value,
        application_id=application_id,
        event_data={
            "document_id": document_id,
            "extraction_id": extraction.id,
            "field_name": extraction.field_name,
            "old_value": correction.old_value,
            "new_value": correction.new_value,
            "old_normalized_value": correction.old_normalized_value,
            "new_normalized_value": correction.new_normalized_value,
            "reason": correction.reason,
        },
    )
    await session.commit()
    await session.refresh(correction)
    await session.refresh(extraction)
    return correction, extraction


async def list_corrections(
    session: AsyncSession,
    user: UserContext,
    *,
    application_id: int,
    document_id: int,
    extraction_id: int,
) -> list[ExtractionCorrection] | None:
    """Return correction history if the caller can access the document."""
    document = await document_service.get_document(session, user, document_id)
    if document is None or document.application_id != application_id:
        return None

    extraction_result = await session.execute(
        select(DocumentExtraction.id).where(
            DocumentExtraction.id == extraction_id,
            DocumentExtraction.document_id == document_id,
        )
    )
    if extraction_result.scalar_one_or_none() is None:
        return None

    result = await session.execute(
        select(ExtractionCorrection)
        .options(selectinload(ExtractionCorrection.extraction))
        .where(ExtractionCorrection.extraction_id == extraction_id)
        .order_by(ExtractionCorrection.corrected_at.asc())
    )
    return list(result.scalars().all())
