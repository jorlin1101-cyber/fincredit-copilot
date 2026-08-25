# This project was developed with assistance from AI tools.
"""Add Chinese full-text tokens for hybrid policy retrieval.

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-08-25
"""

import sqlalchemy as sa

from alembic import op

revision = "f9a0b1c2d3e4"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "kb_chunks",
        sa.Column("search_text", sa.Text(), nullable=False, server_default=""),
    )
    op.execute("UPDATE kb_chunks SET search_text = lower(chunk_text)")
    op.create_index(
        "ix_kb_chunks_search_text_gin",
        "kb_chunks",
        [sa.text("to_tsvector('simple', search_text)")],
        postgresql_using="gin",
    )
    op.alter_column("kb_chunks", "search_text", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_kb_chunks_search_text_gin", table_name="kb_chunks")
    op.drop_column("kb_chunks", "search_text")
