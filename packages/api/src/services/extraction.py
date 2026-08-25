# This project was developed with assistance from AI tools.
"""Document extraction pipeline.

Two-stage extraction: text extraction (pymupdf) then structured extraction
(LLM). Scanned PDFs and images fall back to LLM vision. Post-extraction
HMDA filter routes demographic fields to the compliance schema via
``services.compliance.hmda`` (the sole permitted HMDA accessor).
"""

import asyncio
import base64
import functools
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass

import fitz  # pymupdf
from db import (
    Document,
    DocumentExtraction,
)
from db.database import SessionLocal
from db.enums import DocumentStatus, DocumentType, ExtractionMethod
from pydantic import ValidationError
from sqlalchemy import select

from ..core.config import settings
from ..inference.client import get_completion
from ..schemas.chinese_document import LLMExtractionResponse
from ..services.audit import write_audit_event
from .compliance.hmda import route_extraction_demographics
from .extraction_normalization import normalize_extracted_value
from .extraction_prompts import (
    HMDA_DEMOGRAPHIC_KEYWORDS,
    build_extraction_prompt,
    build_image_extraction_prompt,
)
from .freshness import check_freshness
from .storage import get_storage_service

logger = logging.getLogger(__name__)


def _normalize_doc_type(raw: str) -> str | None:
    """Try to resolve an LLM-returned doc type string to a valid DocumentType value."""
    cleaned = raw.strip().lower().replace(" ", "_").replace("-", "_")
    # Direct match
    try:
        return DocumentType(cleaned).value
    except ValueError:
        pass
    # Substring match (e.g. "insurance" in "homeowners_insurance_policy")
    for dtype in DocumentType:
        if dtype.value != "other" and dtype.value in cleaned:
            return dtype.value
    return None


# Minimum page text length to treat a PDF page as having a useful text layer.
_MIN_TEXT_LENGTH = 20

# Matches ```json ... ``` or ``` ... ``` fences that LLMs often wrap around JSON.
_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?\s*```$", re.DOTALL)


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences wrapping JSON output.

    Many LLMs wrap JSON in ```json ... ``` blocks when not constrained by
    response_format. This strips the fences so json.loads() succeeds.
    """
    stripped = text.strip()
    m = _FENCE_RE.match(stripped)
    return m.group(1).strip() if m else stripped


@dataclass(frozen=True)
class PDFPage:
    """One independently processed PDF page."""

    page_no: int
    text: str
    image_data: bytes | None = None


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _find_evidence_line(page_text: str, field_value: str | None) -> str | None:
    """Find an actual source line containing the model-returned value."""
    if not field_value:
        return None
    needle = _compact_text(field_value)
    if not needle:
        return None
    for line in page_text.splitlines():
        clean_line = line.strip()
        if clean_line and needle in _compact_text(clean_line):
            return clean_line[:500]
    return None


class ExtractionService:
    """Orchestrates download -> extract -> persist for uploaded documents."""

    async def process_document(self, document_id: int) -> None:
        """Main pipeline entry point. Runs as a background task with own DB sessions."""
        async with SessionLocal() as session:
            try:
                stmt = select(Document).where(Document.id == document_id)
                result = await session.execute(stmt)
                doc = result.scalar_one_or_none()
                if doc is None:
                    logger.error("Document %s not found, skipping extraction", document_id)
                    return

                file_path = doc.file_path
                doc_type = doc.doc_type.value
                application_id = doc.application_id
                content_type = self._guess_content_type(file_path)

                # Download from S3
                storage = get_storage_service()
                file_data = await storage.download_file(file_path)

                # Run extraction based on content type
                if content_type == "application/pdf":
                    llm_result = await self._process_pdf(file_data, doc_type)
                else:
                    # JPEG/PNG -> direct to LLM vision
                    llm_result = await self._extract_image_via_llm(
                        file_data, content_type, doc_type
                    )

                if llm_result is None:
                    # Extraction failed (corrupted, unreadable)
                    doc.status = DocumentStatus.PROCESSING_FAILED
                    doc.quality_flags = json.dumps(["unreadable"])
                    await session.commit()
                    return

                extractions = llm_result.get("extractions", [])
                quality_flags = llm_result.get("quality_flags", [])
                detected_doc_type = llm_result.get("detected_doc_type", doc_type)

                # Check for empty extractions (LLM couldn't read)
                if not extractions:
                    doc.status = DocumentStatus.PROCESSING_FAILED
                    doc.quality_flags = json.dumps(["unreadable"])
                    await session.commit()
                    return

                # Auto-reclassify when LLM detects a different document type
                if detected_doc_type and detected_doc_type != doc_type:
                    normalized = _normalize_doc_type(detected_doc_type)
                    if normalized and normalized != doc_type:
                        doc.doc_type = DocumentType(normalized)
                        logger.info(
                            "Reclassified document %d from %s to %s (raw: %s)",
                            document_id,
                            doc_type,
                            normalized,
                            detected_doc_type,
                        )
                    elif not normalized:
                        quality_flags.append("document_type_mismatch")

                # HMDA demographic filter
                lending_extractions, demographic_extractions = self._filter_hmda_fields(extractions)

                # Route demographic data to compliance schema
                if demographic_extractions:
                    await route_extraction_demographics(
                        document_id,
                        application_id,
                        demographic_extractions,
                        borrower_id=doc.borrower_id,
                    )

                # Document freshness check
                freshness_flag = check_freshness(doc_type, lending_extractions)
                if freshness_flag:
                    quality_flags.append(freshness_flag)

                # Store quality flags
                doc.quality_flags = json.dumps(quality_flags) if quality_flags else None

                # Persist lending-path extractions
                for ext in lending_extractions:
                    extraction = DocumentExtraction(
                        document_id=document_id,
                        field_name=ext.get("field_name", ""),
                        field_value=ext.get("field_value"),
                        normalized_value=ext.get("normalized_value"),
                        confidence=ext.get("confidence"),
                        source_page=ext.get("source_page"),
                        evidence_text=ext.get("evidence_text"),
                        extraction_method=(
                            ExtractionMethod(ext["extraction_method"])
                            if ext.get("extraction_method")
                            else None
                        ),
                    )
                    session.add(extraction)

                doc.status = (
                    DocumentStatus.PENDING_REVIEW
                    if "low_confidence" in quality_flags
                    else DocumentStatus.PROCESSING_COMPLETE
                )

                await write_audit_event(
                    session,
                    event_type="document_extraction_complete",
                    application_id=application_id,
                    event_data={
                        "document_id": document_id,
                        "doc_type": doc.doc_type.value,
                        "extraction_count": len(lending_extractions),
                        "source_pages": sorted(
                            {
                                ext["source_page"]
                                for ext in lending_extractions
                                if ext.get("source_page") is not None
                            }
                        ),
                        "low_confidence_fields": [
                            ext["field_name"]
                            for ext in lending_extractions
                            if ext.get("confidence", 0) < settings.EXTRACTION_CONFIDENCE_THRESHOLD
                        ],
                        "quality_flags": quality_flags,
                        "reclassified_from": (doc_type if doc.doc_type.value != doc_type else None),
                    },
                )

                await session.commit()
                logger.info(
                    "Document %s processed: %d extractions, %d flags",
                    document_id,
                    len(lending_extractions),
                    len(quality_flags),
                )

            except Exception as exc:
                logger.exception("Extraction failed for document %s", document_id)
                try:
                    doc.status = DocumentStatus.PROCESSING_FAILED
                    await write_audit_event(
                        session,
                        event_type="document_extraction_failed",
                        application_id=doc.application_id,
                        event_data={
                            "document_id": document_id,
                            "error": str(exc)[:500],
                        },
                    )
                    await session.commit()
                except Exception:
                    logger.exception("Failed to update status for document %s", document_id)

    async def _process_pdf(self, file_data: bytes, doc_type: str) -> dict | None:
        """Process every PDF page independently and merge grounded results."""
        pages = await self._extract_pages_from_pdf(file_data)
        if pages is None:
            return None

        merged_extractions: list[dict] = []
        quality_flags: list[str] = []
        detected_types: list[str] = []

        for page in pages:
            if len(page.text) >= _MIN_TEXT_LENGTH:
                page_result = await self._extract_via_llm(
                    page.text,
                    doc_type,
                    source_page=page.page_no,
                )
            elif page.image_data is not None:
                page_result = await self._extract_image_via_llm(
                    page.image_data,
                    "image/png",
                    doc_type,
                    source_page=page.page_no,
                )
            else:
                page_result = None

            if page_result is None:
                quality_flags.append("page_extraction_failed")
                continue

            merged_extractions.extend(page_result.get("extractions", []))
            quality_flags.extend(page_result.get("quality_flags", []))
            detected = page_result.get("detected_doc_type")
            if detected:
                detected_types.append(detected)

        normalized_types = [value for raw in detected_types if (value := _normalize_doc_type(raw))]
        if len(set(normalized_types)) > 1:
            quality_flags.append("cross_page_document_type_conflict")

        detected_doc_type = doc_type
        if normalized_types:
            detected_doc_type = (
                doc_type
                if doc_type in normalized_types
                else Counter(normalized_types).most_common(1)[0][0]
            )
        elif detected_types:
            # Preserve an unknown raw type so the caller can flag the mismatch.
            detected_doc_type = detected_types[0]

        return {
            "extractions": merged_extractions,
            "quality_flags": _dedupe(quality_flags),
            "detected_doc_type": detected_doc_type,
        }

    async def _extract_pages_from_pdf(self, file_data: bytes) -> list[PDFPage] | None:
        """Extract text per page and render only pages without a useful text layer."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            functools.partial(self._extract_pages_from_pdf_sync, file_data),
        )

    @staticmethod
    def _extract_pages_from_pdf_sync(file_data: bytes) -> list[PDFPage] | None:
        pdf = None
        try:
            pdf = fitz.open(stream=file_data, filetype="pdf")
            pages: list[PDFPage] = []
            for page_index, page in enumerate(pdf):
                page_text = page.get_text().strip()
                image_data = None
                if len(page_text) < _MIN_TEXT_LENGTH:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    image_data = pix.tobytes("png")
                pages.append(
                    PDFPage(
                        page_no=page_index + 1,
                        text=page_text,
                        image_data=image_data,
                    )
                )
            return pages
        except Exception:
            logger.exception("Failed to split PDF into pages")
            return None
        finally:
            if pdf is not None:
                pdf.close()

    async def _extract_text_from_pdf(self, file_data: bytes) -> str | None:
        """Use pymupdf to extract text from all pages.

        Returns None if PDF is corrupted/unopenable.
        Returns empty string if no text layer (scanned doc).
        Runs in executor to avoid blocking the async event loop.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, functools.partial(self._extract_text_from_pdf_sync, file_data)
        )

    @staticmethod
    def _extract_text_from_pdf_sync(file_data: bytes) -> str | None:
        """Synchronous PDF text extraction (runs in thread pool)."""
        pdf = None
        try:
            pdf = fitz.open(stream=file_data, filetype="pdf")
            text_parts = []
            for page in pdf:
                text_parts.append(page.get_text())
            return " ".join(text_parts).strip()
        except Exception:
            logger.exception("Failed to open PDF with pymupdf")
            return None
        finally:
            if pdf is not None:
                pdf.close()

    async def _pdf_first_page_to_image(self, file_data: bytes) -> bytes | None:
        """Render only the first page of a PDF as a PNG image.

        Runs in executor to avoid blocking the async event loop.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, functools.partial(self._pdf_first_page_to_image_sync, file_data)
        )

    @staticmethod
    def _pdf_first_page_to_image_sync(file_data: bytes) -> bytes | None:
        """Synchronous PDF-to-image rendering (runs in thread pool)."""
        pdf = None
        try:
            pdf = fitz.open(stream=file_data, filetype="pdf")
            if len(pdf) == 0:
                return None
            pix = pdf[0].get_pixmap()
            return pix.tobytes("png")
        except Exception:
            logger.exception("Failed to render PDF first page to image")
            return None
        finally:
            if pdf is not None:
                pdf.close()

    async def _extract_via_llm(
        self,
        text: str,
        doc_type: str,
        source_page: int = 1,
    ) -> dict | None:
        """Send text to LLM, get structured extractions + quality flags."""
        messages = build_extraction_prompt(doc_type, text, source_page)
        result = await self._request_validated_completion(messages, tier="llm")
        if result is None:
            return None
        return self._ground_page_result(
            result,
            source_page=source_page,
            method=ExtractionMethod.TEXT_LAYER,
            page_text=text,
        )

    async def _extract_image_via_llm(
        self,
        image_data: bytes,
        content_type: str,
        doc_type: str,
        source_page: int = 1,
    ) -> dict | None:
        """Send image to LLM vision, get structured extractions + quality flags."""
        system_msg = build_image_extraction_prompt(doc_type, source_page)
        b64 = base64.b64encode(image_data).decode("ascii")
        messages = [
            system_msg,
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{content_type};base64,{b64}"},
                    },
                    {"type": "text", "text": "请抽取当前页材料并返回严格 JSON。"},
                ],
            },
        ]
        result = await self._request_validated_completion(messages, tier="vision")
        if result is None:
            return None
        return self._ground_page_result(
            result,
            source_page=source_page,
            method=ExtractionMethod.VISION,
        )

    async def _request_validated_completion(self, messages: list[dict], tier: str) -> dict | None:
        """Request strict JSON and make at most one repair attempt."""
        request_messages = list(messages)
        for attempt in range(2):
            raw = await get_completion(
                request_messages,
                tier=tier,
                response_format={"type": "json_object"},
            )
            try:
                validated = LLMExtractionResponse.model_validate_json(_strip_json_fences(raw))
                return validated.model_dump(mode="json")
            except ValidationError as exc:
                logger.warning(
                    "Invalid extraction JSON on attempt %d: %s",
                    attempt + 1,
                    str(exc).splitlines()[0],
                )
                if attempt == 0:
                    request_messages.extend(
                        [
                            {"role": "assistant", "content": raw[:4000]},
                            {
                                "role": "user",
                                "content": (
                                    "上一次输出未通过 JSON Schema 校验。请只返回修正后的 JSON；"
                                    "每个字段必须包含 field_name、field_value、confidence、"
                                    "source_page 和非空 evidence_text。"
                                ),
                            },
                        ]
                    )
        return None

    @staticmethod
    def _ground_page_result(
        result: dict,
        *,
        source_page: int,
        method: ExtractionMethod,
        page_text: str | None = None,
    ) -> dict:
        """Attach trusted provenance and reject ungrounded text-layer evidence."""
        grounded: list[dict] = []
        quality_flags = list(result.get("quality_flags", []))

        for item in result.get("extractions", []):
            field = dict(item)
            evidence = field.get("evidence_text", "").strip()
            if page_text is not None and _compact_text(evidence) not in _compact_text(page_text):
                evidence = _find_evidence_line(page_text, field.get("field_value")) or ""
                if not evidence:
                    quality_flags.append("evidence_not_found")
                    continue

            field["source_page"] = source_page
            field["evidence_text"] = evidence
            field["extraction_method"] = method.value
            field["normalized_value"] = normalize_extracted_value(
                field["field_name"],
                field.get("field_value"),
            )
            if field["confidence"] < settings.EXTRACTION_CONFIDENCE_THRESHOLD:
                quality_flags.append("low_confidence")
            grounded.append(field)

        return {
            "extractions": grounded,
            "quality_flags": _dedupe(quality_flags),
            "detected_doc_type": result.get("detected_doc_type"),
        }

    def _filter_hmda_fields(
        self,
        extractions: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        """Separate demographic from lending-path extractions.

        Returns (lending_extractions, demographic_extractions).
        """
        lending = []
        demographic = []
        for ext in extractions:
            field_name = ext.get("field_name", "").lower().replace(" ", "_").replace("-", "_")
            if field_name in HMDA_DEMOGRAPHIC_KEYWORDS:
                demographic.append(ext)
            else:
                lending.append(ext)
        return lending, demographic

    @staticmethod
    def _guess_content_type(file_path: str) -> str:
        """Guess content type from file extension in the S3 key."""
        lower = file_path.lower()
        if lower.endswith(".pdf"):
            return "application/pdf"
        if lower.endswith((".jpg", ".jpeg")):
            return "image/jpeg"
        if lower.endswith(".png"):
            return "image/png"
        return "application/pdf"  # default to PDF


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_service: ExtractionService | None = None


def init_extraction_service() -> ExtractionService:
    """Initialise the singleton (called once from app lifespan)."""
    global _service  # noqa: PLW0603
    _service = ExtractionService()
    logger.info("ExtractionService initialised")
    return _service


def get_extraction_service() -> ExtractionService:
    """Return the initialised ExtractionService singleton."""
    if _service is None:
        raise RuntimeError(
            "ExtractionService not initialised -- call init_extraction_service() first"
        )
    return _service
