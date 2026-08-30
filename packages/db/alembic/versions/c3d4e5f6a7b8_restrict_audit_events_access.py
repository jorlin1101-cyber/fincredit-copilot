# This project was developed with assistance from AI tools.
"""restrict audit_events to append-only for lending_app and compliance_app

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-02-24 18:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "a1b2c3d4e5f6"
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
    # The a1b2c3d4e5f6 migration grants GRANT ALL on all public tables to
    # lending_app, which includes UPDATE and DELETE on audit_events. This
    # violates the append-only audit guarantee. Revoke those privileges.
    _execute_if_role_exists("REVOKE UPDATE, DELETE ON audit_events FROM lending_app", "lending_app")
    _execute_if_role_exists("REVOKE UPDATE, DELETE ON audit_events FROM compliance_app", "compliance_app")


def downgrade() -> None:
    _execute_if_role_exists("GRANT UPDATE, DELETE ON audit_events TO lending_app", "lending_app")
    _execute_if_role_exists("GRANT UPDATE, DELETE ON audit_events TO compliance_app", "compliance_app")
