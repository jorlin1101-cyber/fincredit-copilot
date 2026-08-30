# This project was developed with assistance from AI tools.
"""Add append-only extraction correction history.

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-08-25
"""

import sqlalchemy as sa

from alembic import op

revision = "d7e8f9a0b1c2"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None


def _execute_if_role_exists(sql: str, role: str) -> None:
    escaped_sql = sql.replace("'", "''")
    op.execute(
        sa.text(
            f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') "
            f"THEN EXECUTE '{escaped_sql}'; END IF; END $$;"
        )
    )


def upgrade() -> None:
    op.create_table(
        "extraction_corrections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("extraction_id", sa.Integer(), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=False),
        sa.Column("old_normalized_value", sa.Text(), nullable=True),
        sa.Column("new_normalized_value", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("corrected_by", sa.String(length=255), nullable=False),
        sa.Column(
            "corrected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["extraction_id"],
            ["document_extractions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_extraction_corrections_extraction_id",
        "extraction_corrections",
        ["extraction_id"],
    )
    op.create_index(
        "ix_extraction_corrections_corrected_by",
        "extraction_corrections",
        ["corrected_by"],
    )
    _execute_if_role_exists(
        "GRANT SELECT, INSERT ON extraction_corrections TO lending_app", "lending_app"
    )
    _execute_if_role_exists(
        "GRANT USAGE, SELECT ON SEQUENCE extraction_corrections_id_seq TO lending_app", "lending_app"
    )
    _execute_if_role_exists(
        "GRANT SELECT ON extraction_corrections TO compliance_app", "compliance_app"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_extraction_corrections_corrected_by",
        table_name="extraction_corrections",
    )
    op.drop_index(
        "ix_extraction_corrections_extraction_id",
        table_name="extraction_corrections",
    )
    op.drop_table("extraction_corrections")
