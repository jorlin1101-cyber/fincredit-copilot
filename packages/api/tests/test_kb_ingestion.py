# This project was developed with assistance from AI tools.
"""Tests for compliance KB ingestion pipeline."""

import textwrap
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from db import KBChunk, KBDocument, PolicyJurisdiction, PolicySourceType
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.compliance.knowledge_base.ingestion import (
    _chunk_markdown,
    _parse_frontmatter,
    _validated_metadata,
    build_search_text,
    ingest_kb_content,
)


class TestParseFrontmatter:
    """Tests for YAML frontmatter parsing."""

    def test_extracts_title_and_date(self):
        content = textwrap.dedent("""\
            ---
            title: "Test Regulation"
            effective_date: "2024-01-01"
            ---
            Body text here.
        """)
        metadata, body = _parse_frontmatter(content)
        assert metadata["title"] == "Test Regulation"
        assert metadata["effective_date"] == "2024-01-01"

    def test_returns_body_without_frontmatter(self):
        content = textwrap.dedent("""\
            ---
            title: "Test"
            ---
            ## Section One

            Content here.
        """)
        metadata, body = _parse_frontmatter(content)
        assert body.startswith("## Section One")
        assert "---" not in body

    def test_handles_no_frontmatter(self):
        content = "Just plain text with no frontmatter."
        metadata, body = _parse_frontmatter(content)
        assert metadata == {}
        assert body == content

    def test_handles_empty_frontmatter(self):
        content = "---\n---\nBody text."
        metadata, body = _parse_frontmatter(content)
        assert metadata == {}
        assert body == "Body text."


class TestChunkMarkdown:
    """Tests for markdown chunking."""

    def test_splits_on_section_headers(self):
        body = textwrap.dedent("""\
            ## Section One

            Content for section one.

            ## Section Two

            Content for section two.
        """)
        chunks = _chunk_markdown(body)
        assert len(chunks) == 2
        assert "section one" in chunks[0]["text"].lower()
        assert "section two" in chunks[1]["text"].lower()

    def test_preserves_section_ref(self):
        body = textwrap.dedent("""\
            ## DTI Limits

            The maximum DTI ratio is 43%.

            ## Credit Score

            Minimum credit score is 620.
        """)
        chunks = _chunk_markdown(body)
        assert chunks[0]["section_ref"] == "DTI Limits"
        assert chunks[1]["section_ref"] == "Credit Score"

    def test_splits_long_sections(self):
        # Create a section with many paragraphs exceeding target chunk size
        paragraphs = [f"Paragraph {i}. " + "x" * 300 for i in range(20)]
        body = "## Long Section\n\n" + "\n\n".join(paragraphs)
        chunks = _chunk_markdown(body)
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk["section_ref"] == "Long Section"

    def test_handles_content_before_first_header(self):
        body = textwrap.dedent("""\
            Intro text before any headers.

            ## First Section

            Section content.
        """)
        chunks = _chunk_markdown(body)
        assert len(chunks) == 2
        assert chunks[0]["section_ref"] is None or chunks[0]["section_ref"] == ""
        assert chunks[1]["section_ref"] == "First Section"

    def test_empty_body(self):
        chunks = _chunk_markdown("")
        assert chunks == []


def test_build_search_text_supports_chinese_and_financial_terms():
    tokens = build_search_text("成都公积金 DTI 50% 首付款").split()
    assert "成都" in tokens
    assert "都公" in tokens
    assert "dti" in tokens
    assert "50" in tokens
    assert "首付" in tokens


class TestIngestKbContent:
    """Tests for the full ingestion pipeline (mocked DB + embeddings)."""

    @pytest.fixture
    def kb_data_dir(self, tmp_path):
        """Create a temporary KB data directory with test content."""
        tier1 = tmp_path / "tier1-national"
        tier1.mkdir()
        (tier1 / "test-reg.md").write_text(
            textwrap.dedent("""\
            ---
            title: "Test Regulation"
            source_document: "Test Source"
            issuer: "Test Regulator"
            source_url: "https://example.gov.cn/test-reg"
            jurisdiction: "national"
            source_type: "official"
            version: "2026-v1"
            published_date: "2023-12-01"
            effective_date: "2024-01-01"
            expires_at: "2027-01-01"
            retrieved_date: "2026-08-25"
            ---

            DISCLAIMER: Simulated content.

            ## Section A

            Content for section A.

            ## Section B

            Content for section B.
        """)
        )
        tier3 = tmp_path / "tier3-internal-demo"
        tier3.mkdir()
        (tier3 / "test-policy.md").write_text(
            textwrap.dedent("""\
            ---
            title: "Test Policy"
            source_document: "Internal Manual"
            retrieved_date: "2026-08-25"
            ---

            ## Policy Section

            Policy content here.
        """)
        )
        return tmp_path

    @pytest.mark.asyncio
    async def test_creates_documents_and_chunks(self, kb_data_dir, monkeypatch):
        """Ingestion creates KBDocument and KBChunk rows with embeddings."""
        mock_session = AsyncMock(spec=AsyncSession)
        added_objects = []
        mock_session.add = lambda x: added_objects.append(x)
        mock_session.flush = AsyncMock()

        fake_embeddings = [[0.1] * 768, [0.2] * 768, [0.3] * 768]
        mock_embed = AsyncMock(return_value=fake_embeddings)

        import src.services.compliance.knowledge_base.ingestion as mod

        monkeypatch.setattr(mod, "get_embeddings", mock_embed)

        result = await ingest_kb_content(mock_session, data_root=kb_data_dir)

        assert result["documents"] == 2  # test-reg.md + test-policy.md
        assert result["chunks"] >= 3  # at least 3 chunks across both files
        assert mock_embed.call_count >= 1

        documents = [obj for obj in added_objects if isinstance(obj, KBDocument)]
        official = next(doc for doc in documents if doc.title == "Test Regulation")
        assert official.issuer == "Test Regulator"
        assert official.source_url == "https://example.gov.cn/test-reg"
        assert official.jurisdiction == PolicyJurisdiction.NATIONAL
        assert official.source_type == PolicySourceType.OFFICIAL
        assert official.version == "2026-v1"
        assert official.published_date.isoformat().startswith("2023-12-01")
        assert official.expires_at.isoformat().startswith("2027-01-01")
        assert official.retrieved_at.isoformat().startswith("2026-08-25")
        assert len(official.content_hash) == 64

        internal = next(doc for doc in documents if doc.title == "Test Policy")
        assert internal.jurisdiction == PolicyJurisdiction.INTERNAL_DEMO
        assert internal.source_type == PolicySourceType.INTERNAL_DEMO

    @pytest.mark.asyncio
    async def test_handles_embedding_failure(self, kb_data_dir, monkeypatch):
        """When embedding fails, chunks are stored with None embedding."""
        mock_session = AsyncMock(spec=AsyncSession)
        added_objects = []
        mock_session.add = lambda x: added_objects.append(x)
        mock_session.flush = AsyncMock()

        mock_embed = AsyncMock(side_effect=RuntimeError("No embedding model"))

        import src.services.compliance.knowledge_base.ingestion as mod

        monkeypatch.setattr(mod, "get_embeddings", mock_embed)

        result = await ingest_kb_content(mock_session, data_root=kb_data_dir)

        assert result["documents"] == 2
        assert result["chunks"] >= 3

        # Verify chunks were added without embeddings
        chunk_objects = [o for o in added_objects if isinstance(o, KBChunk)]
        for chunk in chunk_objects:
            assert chunk.embedding is None


def test_shipped_chinese_policy_corpus_has_valid_provenance():
    root = Path(__file__).resolve().parents[3] / "data" / "compliance-kb"
    tier_dirs = {
        1: "tier1-national",
        2: "tier2-chengdu",
        3: "tier3-internal-demo",
    }
    validated = []
    for tier, directory in tier_dirs.items():
        for path in (root / directory).glob("*.md"):
            metadata, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
            validated.append(_validated_metadata(metadata, tier=tier, filename=path.name))
            assert body

    assert len(validated) == 6
    assert sum(item.jurisdiction == PolicyJurisdiction.NATIONAL for item in validated) == 2
    assert sum(item.jurisdiction == PolicyJurisdiction.CHENGDU for item in validated) == 3
    assert sum(item.source_type == PolicySourceType.INTERNAL_DEMO for item in validated) == 1
