# This project was developed with assistance from AI tools.
"""Add deterministic assessment evidence and human-review boundary.

Revision ID: a0b1c2d3e4f5
Revises: f9a0b1c2d3e4
Create Date: 2026-08-25
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "a0b1c2d3e4f5"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("risk_assessments", sa.Column("rule_version", sa.String(100), nullable=True))
    op.add_column(
        "risk_assessments", sa.Column("calculation_inputs", postgresql.JSONB(), nullable=True)
    )
    op.add_column("risk_assessments", sa.Column("rule_results", postgresql.JSONB(), nullable=True))
    op.add_column(
        "risk_assessments", sa.Column("document_completeness", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "risk_assessments", sa.Column("consistency_result", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "risk_assessments",
        sa.Column("human_review_required", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("risk_assessments", sa.Column("trace_id", sa.String(100), nullable=True))
    op.create_index("ix_risk_assessments_trace_id", "risk_assessments", ["trace_id"])


def downgrade() -> None:
    op.drop_index("ix_risk_assessments_trace_id", table_name="risk_assessments")
    op.drop_column("risk_assessments", "trace_id")
    op.drop_column("risk_assessments", "human_review_required")
    op.drop_column("risk_assessments", "consistency_result")
    op.drop_column("risk_assessments", "document_completeness")
    op.drop_column("risk_assessments", "rule_results")
    op.drop_column("risk_assessments", "calculation_inputs")
    op.drop_column("risk_assessments", "rule_version")
