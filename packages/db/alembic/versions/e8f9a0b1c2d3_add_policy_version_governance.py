# This project was developed with assistance from AI tools.
"""Add policy retrieval timestamp and immutable content fingerprint.

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-08-25
"""

import sqlalchemy as sa

from alembic import op

revision = "e8f9a0b1c2d3"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "kb_documents", sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "kb_documents",
        sa.Column("content_hash", sa.String(length=64), nullable=False, server_default="legacy"),
    )
    op.create_index("ix_kb_documents_content_hash", "kb_documents", ["content_hash"])
    op.alter_column("kb_documents", "content_hash", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_kb_documents_content_hash", table_name="kb_documents")
    op.drop_column("kb_documents", "content_hash")
    op.drop_column("kb_documents", "retrieved_at")
