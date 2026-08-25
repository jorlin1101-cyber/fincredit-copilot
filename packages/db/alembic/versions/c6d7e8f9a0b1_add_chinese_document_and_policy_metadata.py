# This project was developed with assistance from AI tools.
"""Add Chinese document evidence fields and policy provenance metadata.

Revision ID: c6d7e8f9a0b1
Revises: 3f0a759b847d
Create Date: 2026-08-25
"""

import sqlalchemy as sa

from alembic import op

revision = "c6d7e8f9a0b1"
down_revision = "3f0a759b847d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_extractions", sa.Column("normalized_value", sa.Text(), nullable=True))
    op.add_column("document_extractions", sa.Column("evidence_text", sa.Text(), nullable=True))
    op.add_column(
        "document_extractions",
        sa.Column("extraction_method", sa.String(length=20), nullable=True),
    )

    op.add_column("kb_documents", sa.Column("issuer", sa.String(length=500), nullable=True))
    op.add_column("kb_documents", sa.Column("source_url", sa.String(length=2000), nullable=True))
    op.add_column(
        "kb_documents",
        sa.Column(
            "jurisdiction",
            sa.String(length=20),
            nullable=False,
            server_default="national",
        ),
    )
    op.add_column(
        "kb_documents",
        sa.Column(
            "source_type",
            sa.String(length=20),
            nullable=False,
            server_default="official",
        ),
    )
    op.add_column("kb_documents", sa.Column("version", sa.String(length=100), nullable=True))
    op.add_column(
        "kb_documents",
        sa.Column("published_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "kb_documents",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_kb_documents_jurisdiction", "kb_documents", ["jurisdiction"])
    op.create_index("ix_kb_documents_source_type", "kb_documents", ["source_type"])

    # Existing tier-2/3 rows receive honest provenance defaults until the
    # versioned Chinese corpus replaces the upstream sample content in D6.
    op.execute("UPDATE kb_documents SET jurisdiction = 'chengdu' WHERE tier = 2")
    op.execute(
        "UPDATE kb_documents SET jurisdiction = 'internal_demo', "
        "source_type = 'internal_demo' WHERE tier = 3"
    )


def downgrade() -> None:
    op.drop_index("ix_kb_documents_source_type", table_name="kb_documents")
    op.drop_index("ix_kb_documents_jurisdiction", table_name="kb_documents")
    op.drop_column("kb_documents", "expires_at")
    op.drop_column("kb_documents", "published_date")
    op.drop_column("kb_documents", "version")
    op.drop_column("kb_documents", "source_type")
    op.drop_column("kb_documents", "jurisdiction")
    op.drop_column("kb_documents", "source_url")
    op.drop_column("kb_documents", "issuer")
    op.drop_column("document_extractions", "extraction_method")
    op.drop_column("document_extractions", "evidence_text")
    op.drop_column("document_extractions", "normalized_value")
