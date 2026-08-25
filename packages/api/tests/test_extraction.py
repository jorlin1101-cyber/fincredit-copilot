# This project was developed with assistance from AI tools.
"""Unit tests for the document extraction pipeline.

All LLM calls and S3 downloads are mocked. Tests cover:
- PDF text extraction (pymupdf)
- Corrupted PDF handling
- Scanned PDF fallback to image extraction
- LLM text/image extraction
- Malformed JSON handling
- Empty extractions handling
- Full pipeline happy paths (PDF + image)
- Error handling (PROCESSING_FAILED)
- HMDA demographic field filtering
- HMDA routing to compliance schema
- HMDA exclusion audit logging
- Quality flags persistence
- Document type mismatch detection
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from db.enums import DocumentType
from openai import BadRequestError

from src.services.extraction import ExtractionService, _strip_json_fences

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_doc(
    doc_id=1,
    file_path="101/1/test.pdf",
    doc_type_value="w2",
    application_id=101,
    status="processing",
    borrower_id=10,
):
    """Build a mock Document ORM object for extraction tests."""
    doc = MagicMock()
    doc.id = doc_id
    doc.file_path = file_path
    doc.doc_type.value = doc_type_value
    doc.application_id = application_id
    doc.status = status
    doc.quality_flags = None
    doc.borrower_id = borrower_id
    return doc


def _llm_response(
    extractions=None,
    quality_flags=None,
    detected_doc_type="w2",
):
    """Build a JSON string matching the expected LLM output."""
    return json.dumps(
        {
            "extractions": extractions
            or [
                {
                    "field_name": "employer_name",
                    "field_value": "Acme Corp",
                    "confidence": 0.95,
                    "source_page": 1,
                    "evidence_text": "Acme Corp",
                },
                {
                    "field_name": "wages",
                    "field_value": "85000",
                    "confidence": 0.90,
                    "source_page": 1,
                    "evidence_text": "85000",
                },
            ],
            "quality_flags": quality_flags or [],
            "detected_doc_type": detected_doc_type,
        }
    )


# Minimal valid PDF (1 page with text "Hello World")
_MINIMAL_PDF = None


def _get_minimal_pdf():
    """Create a minimal valid PDF with text using pymupdf."""
    global _MINIMAL_PDF
    if _MINIMAL_PDF is None:
        import fitz

        pdf = fitz.open()
        page = pdf.new_page()
        page.insert_text((72, 72), "Hello World employer_name Acme Corp wages 85000 tax_year 2025")
        _MINIMAL_PDF = pdf.tobytes()
        pdf.close()
    return _MINIMAL_PDF


def _get_blank_pdf():
    """Create a valid PDF with no text (simulates scanned doc)."""
    import fitz

    pdf = fitz.open()
    pdf.new_page()
    data = pdf.tobytes()
    pdf.close()
    return data


def _get_mixed_two_page_pdf():
    """Create one text page followed by one scanned/blank page."""
    import fitz

    pdf = fitz.open()
    text_page = pdf.new_page()
    text_page.insert_text((72, 72), "Employee Name: Zhang Chen\nMonthly Income: 20000 yuan")
    pdf.new_page()
    data = pdf.tobytes()
    pdf.close()
    return data


# ---------------------------------------------------------------------------
# JSON fence stripping
# ---------------------------------------------------------------------------


class TestStripJsonFences:
    """_strip_json_fences handles markdown code fences around JSON."""

    def test_clean_json_unchanged(self):
        raw = '{"extractions": []}'
        assert _strip_json_fences(raw) == raw

    def test_strips_json_fence(self):
        fenced = '```json\n{"key": "value"}\n```'
        assert _strip_json_fences(fenced) == '{"key": "value"}'

    def test_strips_plain_fence(self):
        fenced = '```\n{"key": "value"}\n```'
        assert _strip_json_fences(fenced) == '{"key": "value"}'

    def test_strips_with_surrounding_whitespace(self):
        fenced = '  \n```json\n{"key": "value"}\n```\n  '
        assert _strip_json_fences(fenced) == '{"key": "value"}'

    def test_non_json_fence_left_alone(self):
        fenced = '```python\nprint("hello")\n```'
        # Doesn't match our pattern (only strips json or no-lang fences)
        assert "print" in _strip_json_fences(fenced)


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------


class TestExtractTextFromPdf:
    """pymupdf text extraction from PDF bytes."""

    def test_extract_text_from_pdf(self):
        result = ExtractionService._extract_text_from_pdf_sync(_get_minimal_pdf())
        assert result is not None
        assert "Hello World" in result
        assert len(result) >= 50

    def test_corrupted_pdf_returns_none(self):
        result = ExtractionService._extract_text_from_pdf_sync(b"not a pdf at all")
        assert result is None

    def test_blank_pdf_returns_short_text(self):
        result = ExtractionService._extract_text_from_pdf_sync(_get_blank_pdf())
        assert result is not None
        assert len(result) < 50

    def test_pdf_is_split_and_scanned_page_is_rendered(self):
        pages = ExtractionService._extract_pages_from_pdf_sync(_get_mixed_two_page_pdf())
        assert pages is not None
        assert [page.page_no for page in pages] == [1, 2]
        assert "Monthly Income" in pages[0].text
        assert pages[0].image_data is None
        assert pages[1].text == ""
        assert pages[1].image_data is not None


# ---------------------------------------------------------------------------
# Scanned PDF fallback
# ---------------------------------------------------------------------------


class TestScannedPdfFallback:
    """Scanned PDFs (no text layer) fall back to image extraction."""

    @pytest.mark.asyncio
    async def test_scanned_pdf_falls_back_to_image_extraction(self):
        svc = ExtractionService()
        blank_pdf = _get_blank_pdf()

        with patch.object(svc, "_extract_image_via_llm", new_callable=AsyncMock) as mock_vision:
            mock_vision.return_value = {
                "extractions": [
                    {
                        "field_name": "employer_name",
                        "field_value": "Acme",
                        "confidence": 0.8,
                        "source_page": 1,
                        "evidence_text": "Acme",
                        "normalized_value": "acme",
                        "extraction_method": "vision",
                    }
                ],
                "quality_flags": [],
                "detected_doc_type": "w2",
            }
            result = await svc._process_pdf(blank_pdf, "w2")

        assert result is not None
        assert result["extractions"][0]["field_name"] == "employer_name"
        mock_vision.assert_called_once()

    @pytest.mark.asyncio
    async def test_mixed_pdf_processes_every_page_with_correct_method(self):
        svc = ExtractionService()
        text_result = {
            "extractions": [
                {
                    "field_name": "employee_name",
                    "field_value": "Zhang Chen",
                    "normalized_value": "zhangchen",
                    "confidence": 0.95,
                    "source_page": 1,
                    "evidence_text": "Employee Name: Zhang Chen",
                    "extraction_method": "text_layer",
                }
            ],
            "quality_flags": [],
            "detected_doc_type": "income_certificate",
        }
        vision_result = {
            "extractions": [
                {
                    "field_name": "monthly_gross_income",
                    "field_value": "20000",
                    "normalized_value": "20000.00",
                    "confidence": 0.91,
                    "source_page": 2,
                    "evidence_text": "月收入 20000 元",
                    "extraction_method": "vision",
                }
            ],
            "quality_flags": [],
            "detected_doc_type": "income_certificate",
        }

        with (
            patch.object(
                svc,
                "_extract_via_llm",
                new_callable=AsyncMock,
                return_value=text_result,
            ) as mock_text,
            patch.object(
                svc,
                "_extract_image_via_llm",
                new_callable=AsyncMock,
                return_value=vision_result,
            ) as mock_vision,
        ):
            result = await svc._process_pdf(_get_mixed_two_page_pdf(), "income_certificate")

        assert result is not None
        assert [item["source_page"] for item in result["extractions"]] == [1, 2]
        assert {item["extraction_method"] for item in result["extractions"]} == {
            "text_layer",
            "vision",
        }
        assert mock_text.call_args.kwargs["source_page"] == 1
        assert mock_vision.call_args.kwargs["source_page"] == 2


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------


class TestLlmExtraction:
    """LLM-based text extraction."""

    @pytest.mark.asyncio
    async def test_extract_via_llm_returns_structured_data(self):
        svc = ExtractionService()
        with patch("src.services.extraction.get_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _llm_response()
            result = await svc._extract_via_llm("Employer Acme Corp, wages 85000", "w2")

        assert result is not None
        assert len(result["extractions"]) == 2
        assert result["extractions"][0]["field_name"] == "employer_name"

    @pytest.mark.asyncio
    async def test_extract_via_llm_handles_malformed_json(self):
        svc = ExtractionService()
        with patch("src.services.extraction.get_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "not valid json {{"
            result = await svc._extract_via_llm("Employer Acme Corp, wages 85000", "w2")

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_via_llm_strips_markdown_fences(self):
        """LLM wraps JSON in ```json ... ``` fences -> still parses correctly."""
        svc = ExtractionService()
        fenced = "```json\n" + _llm_response() + "\n```"
        with patch("src.services.extraction.get_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = fenced
            result = await svc._extract_via_llm("Employer Acme Corp, wages 85000", "w2")

        assert result is not None
        assert len(result["extractions"]) == 2
        assert result["extractions"][0]["field_name"] == "employer_name"

    @pytest.mark.asyncio
    async def test_extract_via_llm_strips_plain_fences(self):
        """LLM wraps JSON in ``` ... ``` fences (no language tag) -> still parses."""
        svc = ExtractionService()
        fenced = "```\n" + _llm_response() + "\n```"
        with patch("src.services.extraction.get_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = fenced
            result = await svc._extract_via_llm("Employer Acme Corp, wages 85000", "w2")

        assert result is not None
        assert result["extractions"][0]["field_name"] == "employer_name"

    @pytest.mark.asyncio
    async def test_invalid_schema_is_repaired_once(self):
        svc = ExtractionService()
        invalid = '{"extractions": [{"field_name": "wages"}]}'
        with patch("src.services.extraction.get_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = [invalid, _llm_response()]
            result = await svc._extract_via_llm(
                "Acme Corp reported wages of 85000",
                "w2",
            )

        assert result is not None
        assert mock_llm.call_count == 2

    @pytest.mark.asyncio
    async def test_text_page_provenance_overrides_model_page(self):
        svc = ExtractionService()
        response = json.loads(_llm_response())
        for extraction in response["extractions"]:
            extraction["source_page"] = 99
        with patch(
            "src.services.extraction.get_completion",
            new_callable=AsyncMock,
            return_value=json.dumps(response),
        ):
            result = await svc._extract_via_llm(
                "Acme Corp reported wages of 85000",
                "w2",
                source_page=3,
            )

        assert result is not None
        assert {item["source_page"] for item in result["extractions"]} == {3}
        assert {item["extraction_method"] for item in result["extractions"]} == {"text_layer"}
        wages = next(item for item in result["extractions"] if item["field_name"] == "wages")
        assert wages["normalized_value"] == "85000.00"

    @pytest.mark.asyncio
    async def test_llm_returns_empty_extractions(self):
        """Empty extractions list from LLM -> pipeline sets unreadable + FAILED."""
        svc = ExtractionService()

        mock_doc = _make_mock_doc(file_path="101/1/test.pdf")

        mock_session = AsyncMock()
        mock_session.add = MagicMock()  # session.add() is synchronous
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_storage = MagicMock()
        mock_storage.download_file = AsyncMock(return_value=_get_minimal_pdf())

        with (
            patch("src.services.extraction.SessionLocal") as mock_session_cls,
            patch("src.services.extraction.get_storage_service", return_value=mock_storage),
            patch("src.services.extraction.get_completion", new_callable=AsyncMock) as mock_llm,
        ):
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_llm.return_value = json.dumps(
                {
                    "extractions": [],
                    "quality_flags": [],
                    "detected_doc_type": "w2",
                }
            )

            await svc.process_document(1)

        assert mock_doc.status.name == "PROCESSING_FAILED" or mock_doc.status == "PROCESSING_FAILED"
        flags = json.loads(mock_doc.quality_flags)
        assert "unreadable" in flags


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


class TestProcessDocumentPipeline:
    """Full process_document pipeline with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_process_document_pdf_happy_path(self):
        svc = ExtractionService()
        mock_doc = _make_mock_doc()

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_storage = MagicMock()
        mock_storage.download_file = AsyncMock(return_value=_get_minimal_pdf())

        with (
            patch("src.services.extraction.SessionLocal") as mock_session_cls,
            patch("src.services.extraction.get_storage_service", return_value=mock_storage),
            patch("src.services.extraction.get_completion", new_callable=AsyncMock) as mock_llm,
        ):
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_llm.return_value = _llm_response()

            await svc.process_document(1)

        # Document should be marked PROCESSING_COMPLETE
        from db.enums import DocumentStatus

        assert mock_doc.status == DocumentStatus.PROCESSING_COMPLETE
        mock_session.commit.assert_called()
        # Extractions should have been added
        assert mock_session.add.call_count >= 2

    @pytest.mark.asyncio
    async def test_process_document_image_happy_path(self):
        svc = ExtractionService()
        mock_doc = _make_mock_doc(file_path="101/1/photo.jpg")

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_storage = MagicMock()
        mock_storage.download_file = AsyncMock(return_value=b"\xff\xd8\xff fake jpeg")

        with (
            patch("src.services.extraction.SessionLocal") as mock_session_cls,
            patch("src.services.extraction.get_storage_service", return_value=mock_storage),
            patch("src.services.extraction.get_completion", new_callable=AsyncMock) as mock_llm,
        ):
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_llm.return_value = _llm_response()

            await svc.process_document(1)

        from db.enums import DocumentStatus

        assert mock_doc.status == DocumentStatus.PROCESSING_COMPLETE

    @pytest.mark.asyncio
    async def test_process_document_sets_failed_on_error(self):
        svc = ExtractionService()
        mock_doc = _make_mock_doc()

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_storage = MagicMock()
        mock_storage.download_file = AsyncMock(return_value=_get_minimal_pdf())

        with (
            patch("src.services.extraction.SessionLocal") as mock_session_cls,
            patch("src.services.extraction.get_storage_service", return_value=mock_storage),
            patch("src.services.extraction.get_completion", new_callable=AsyncMock) as mock_llm,
        ):
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_llm.side_effect = RuntimeError("LLM connection failed")

            await svc.process_document(1)

        from db.enums import DocumentStatus

        assert mock_doc.status == DocumentStatus.PROCESSING_FAILED

    @pytest.mark.asyncio
    async def test_process_document_sets_failed_on_bad_request(self):
        """Provider rejects request (e.g. unsupported response_format) -> PROCESSING_FAILED."""
        svc = ExtractionService()
        mock_doc = _make_mock_doc()

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_storage = MagicMock()
        mock_storage.download_file = AsyncMock(return_value=_get_minimal_pdf())

        # Simulate the exact error we hit with LM Studio
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {}
        mock_response.json.return_value = {
            "error": "'response_format.type' must be 'json_schema' or 'text'"
        }

        with (
            patch("src.services.extraction.SessionLocal") as mock_session_cls,
            patch("src.services.extraction.get_storage_service", return_value=mock_storage),
            patch("src.services.extraction.get_completion", new_callable=AsyncMock) as mock_llm,
        ):
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_llm.side_effect = BadRequestError(
                message="'response_format.type' must be 'json_schema' or 'text'",
                response=mock_response,
                body={"error": "'response_format.type' must be 'json_schema' or 'text'"},
            )

            await svc.process_document(1)

        from db.enums import DocumentStatus

        assert mock_doc.status == DocumentStatus.PROCESSING_FAILED


# ---------------------------------------------------------------------------
# HMDA filter
# ---------------------------------------------------------------------------


class TestHmdaFilter:
    """HMDA demographic field separation."""

    def test_hmda_filter_separates_demographic_fields(self):
        svc = ExtractionService()
        extractions = [
            {"field_name": "employer_name", "field_value": "Acme Corp"},
            {"field_name": "wages", "field_value": "85000"},
            {"field_name": "race", "field_value": "Asian"},
            {"field_name": "ethnicity", "field_value": "Not Hispanic"},
            {"field_name": "sex", "field_value": "Male"},
            {"field_name": "age", "field_value": "35"},
        ]
        lending, demographic = svc._filter_hmda_fields(extractions)
        assert len(lending) == 2
        assert len(demographic) == 4
        assert all(e["field_name"] in ("employer_name", "wages") for e in lending)
        assert all(e["field_name"] in ("race", "ethnicity", "sex", "age") for e in demographic)

    def test_hmda_filter_normalizes_llm_field_names(self):
        """LLMs return space/hyphen-separated names; filter must still catch them."""
        svc = ExtractionService()
        extractions = [
            {"field_name": "employer_name", "field_value": "Acme Corp"},
            {"field_name": "Age-Group", "field_value": "30-40"},
            {"field_name": "Gender", "field_value": "Female"},
        ]
        lending, demographic = svc._filter_hmda_fields(extractions)
        assert len(lending) == 1
        assert lending[0]["field_name"] == "employer_name"
        assert len(demographic) == 2

    def test_marital_status_not_filtered(self):
        """marital_status is not a key HMDA demographic -- flows to lending path."""
        svc = ExtractionService()
        extractions = [
            {"field_name": "employer_name", "field_value": "Acme Corp"},
            {"field_name": "marital_status", "field_value": "Married"},
            {"field_name": "national_origin", "field_value": "US"},
            {"field_name": "disability", "field_value": "None"},
        ]
        lending, demographic = svc._filter_hmda_fields(extractions)
        assert len(lending) == 4
        assert len(demographic) == 0

    def test_hmda_no_demographics_no_audit(self):
        svc = ExtractionService()
        extractions = [
            {"field_name": "employer_name", "field_value": "Acme Corp"},
            {"field_name": "wages", "field_value": "85000"},
        ]
        lending, demographic = svc._filter_hmda_fields(extractions)
        assert len(lending) == 2
        assert len(demographic) == 0


class TestHmdaRouting:
    """HMDA data routing to compliance schema and audit logging.

    The actual routing lives in services/compliance/hmda.py (HMDA isolation).
    These tests mock ComplianceSessionLocal at that module path.
    """

    @pytest.mark.asyncio
    async def test_hmda_routes_to_compliance_schema(self):
        from src.services.compliance.hmda import route_extraction_demographics

        demographic_extractions = [
            {"field_name": "race", "field_value": "Asian"},
            {"field_name": "sex", "field_value": "Male"},
            {"field_name": "age", "field_value": "35"},
        ]

        mock_compliance_session = AsyncMock()
        mock_compliance_session.add = MagicMock()
        # _upsert_demographics does a SELECT -- no existing row
        upsert_result = MagicMock()
        upsert_result.scalar_one_or_none.return_value = None
        mock_compliance_session.execute = AsyncMock(return_value=upsert_result)

        with patch("src.services.compliance.hmda.ComplianceSessionLocal") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_compliance_session)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await route_extraction_demographics(1, 101, demographic_extractions)

        # Should have added HmdaDemographic (from upsert) + AuditEvent
        assert mock_compliance_session.add.call_count == 2
        mock_compliance_session.commit.assert_called_once()

        # Check the HmdaDemographic was created with correct fields
        hmda_call = mock_compliance_session.add.call_args_list[0]
        hmda_obj = hmda_call[0][0]
        assert hmda_obj.application_id == 101
        assert hmda_obj.race_method == "document_extraction"
        assert hmda_obj.race == "Asian"
        assert hmda_obj.sex == "Male"
        assert hmda_obj.age == "35"

    @pytest.mark.asyncio
    async def test_hmda_exclusion_creates_audit_event(self):
        from src.services.compliance.hmda import route_extraction_demographics

        demographic_extractions = [
            {"field_name": "race", "field_value": "Asian"},
        ]

        mock_compliance_session = AsyncMock()
        mock_compliance_session.add = MagicMock()
        # _upsert_demographics does a SELECT -- no existing row
        upsert_result = MagicMock()
        upsert_result.scalar_one_or_none.return_value = None
        mock_compliance_session.execute = AsyncMock(return_value=upsert_result)

        with patch("src.services.compliance.hmda.ComplianceSessionLocal") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_compliance_session)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await route_extraction_demographics(1, 101, demographic_extractions)

        # Second add call is the AuditEvent
        audit_call = mock_compliance_session.add.call_args_list[1]
        audit_obj = audit_call[0][0]
        assert audit_obj.event_type == "hmda_document_extraction"
        assert audit_obj.application_id == 101
        assert isinstance(audit_obj.event_data, dict)
        assert audit_obj.event_data["document_id"] == 1
        assert audit_obj.event_data["excluded_fields"][0]["field_name"] == "race"
        assert audit_obj.event_data["detection_method"] == "keyword_match"
        assert audit_obj.event_data["routed_to"] == "hmda.demographics"
        assert "borrower_id" in audit_obj.event_data
        assert "conflicts" in audit_obj.event_data

    @pytest.mark.asyncio
    async def test_extraction_passes_null_borrower_id(self):
        """borrower_id=None from Document flows as None to route_extraction_demographics."""
        from src.services.compliance.hmda import route_extraction_demographics

        demographic_extractions = [
            {"field_name": "race", "field_value": "Asian"},
        ]

        mock_compliance_session = AsyncMock()
        mock_compliance_session.add = MagicMock()
        upsert_result = MagicMock()
        upsert_result.scalar_one_or_none.return_value = None
        mock_compliance_session.execute = AsyncMock(return_value=upsert_result)

        with patch("src.services.compliance.hmda.ComplianceSessionLocal") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_compliance_session)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await route_extraction_demographics(1, 101, demographic_extractions, borrower_id=None)

        # HmdaDemographic should have borrower_id=None
        hmda_call = mock_compliance_session.add.call_args_list[0]
        hmda_obj = hmda_call[0][0]
        assert hmda_obj.borrower_id is None

        # Audit event also records borrower_id=None
        audit_call = mock_compliance_session.add.call_args_list[1]
        audit_obj = audit_call[0][0]
        assert isinstance(audit_obj.event_data, dict)
        assert audit_obj.event_data["borrower_id"] is None

    @pytest.mark.asyncio
    async def test_extraction_passes_borrower_id(self):
        """borrower_id from Document flows to route_extraction_demographics."""
        from src.services.compliance.hmda import route_extraction_demographics

        demographic_extractions = [
            {"field_name": "race", "field_value": "Asian"},
        ]

        mock_compliance_session = AsyncMock()
        mock_compliance_session.add = MagicMock()
        upsert_result = MagicMock()
        upsert_result.scalar_one_or_none.return_value = None
        mock_compliance_session.execute = AsyncMock(return_value=upsert_result)

        with patch("src.services.compliance.hmda.ComplianceSessionLocal") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_compliance_session)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await route_extraction_demographics(1, 101, demographic_extractions, borrower_id=42)

        # Check HmdaDemographic has borrower_id
        hmda_call = mock_compliance_session.add.call_args_list[0]
        hmda_obj = hmda_call[0][0]
        assert hmda_obj.borrower_id == 42

        # Audit event also includes borrower_id
        audit_call = mock_compliance_session.add.call_args_list[1]
        audit_obj = audit_call[0][0]
        assert isinstance(audit_obj.event_data, dict)
        assert audit_obj.event_data["borrower_id"] == 42


# ---------------------------------------------------------------------------
# Quality flags
# ---------------------------------------------------------------------------


class TestQualityFlags:
    """Quality flag persistence and document type mismatch detection."""

    @pytest.mark.asyncio
    async def test_quality_flags_stored_on_document(self):
        svc = ExtractionService()
        mock_doc = _make_mock_doc()

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_storage = MagicMock()
        mock_storage.download_file = AsyncMock(return_value=_get_minimal_pdf())

        with (
            patch("src.services.extraction.SessionLocal") as mock_session_cls,
            patch("src.services.extraction.get_storage_service", return_value=mock_storage),
            patch("src.services.extraction.get_completion", new_callable=AsyncMock) as mock_llm,
        ):
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_llm.return_value = _llm_response(quality_flags=["blurry", "incomplete"])

            await svc.process_document(1)

        flags = json.loads(mock_doc.quality_flags)
        assert "blurry" in flags
        assert "incomplete" in flags

    @pytest.mark.asyncio
    async def test_low_confidence_field_requires_human_review(self):
        svc = ExtractionService()
        mock_doc = _make_mock_doc()
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_storage = MagicMock()
        mock_storage.download_file = AsyncMock(return_value=_get_minimal_pdf())
        low_confidence = _llm_response(
            extractions=[
                {
                    "field_name": "wages",
                    "field_value": "85000",
                    "confidence": 0.55,
                    "source_page": 1,
                    "evidence_text": "wages 85000",
                }
            ]
        )

        with (
            patch("src.services.extraction.SessionLocal") as mock_session_cls,
            patch("src.services.extraction.get_storage_service", return_value=mock_storage),
            patch(
                "src.services.extraction.get_completion",
                new_callable=AsyncMock,
                return_value=low_confidence,
            ),
        ):
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await svc.process_document(1)

        from db.enums import DocumentStatus

        assert mock_doc.status == DocumentStatus.PENDING_REVIEW
        assert "low_confidence" in json.loads(mock_doc.quality_flags)

    @pytest.mark.asyncio
    async def test_document_type_reclassified_on_mismatch(self):
        """When LLM detects a different valid doc type, auto-reclassify."""
        svc = ExtractionService()
        mock_doc = _make_mock_doc()

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_storage = MagicMock()
        mock_storage.download_file = AsyncMock(return_value=_get_minimal_pdf())

        with (
            patch("src.services.extraction.SessionLocal") as mock_session_cls,
            patch("src.services.extraction.get_storage_service", return_value=mock_storage),
            patch("src.services.extraction.get_completion", new_callable=AsyncMock) as mock_llm,
            patch("src.services.extraction.write_audit_event", new_callable=AsyncMock),
        ):
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            # Declared type is w2 but LLM detects pay_stub
            mock_llm.return_value = _llm_response(detected_doc_type="pay_stub")

            await svc.process_document(1)

        # Doc type should be reclassified, not flagged
        assert mock_doc.doc_type == DocumentType.PAY_STUB

    async def test_document_type_mismatch_flagged_for_unknown_type(self):
        """When LLM detects a type that can't be normalized, flag mismatch."""
        svc = ExtractionService()
        mock_doc = _make_mock_doc()

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_storage = MagicMock()
        mock_storage.download_file = AsyncMock(return_value=_get_minimal_pdf())

        with (
            patch("src.services.extraction.SessionLocal") as mock_session_cls,
            patch("src.services.extraction.get_storage_service", return_value=mock_storage),
            patch("src.services.extraction.get_completion", new_callable=AsyncMock) as mock_llm,
            patch("src.services.extraction.write_audit_event", new_callable=AsyncMock),
        ):
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            # LLM detects a type that can't be normalized
            mock_llm.return_value = _llm_response(detected_doc_type="unknown_xyz_doc")

            await svc.process_document(1)

        flags = json.loads(mock_doc.quality_flags)
        assert "document_type_mismatch" in flags
