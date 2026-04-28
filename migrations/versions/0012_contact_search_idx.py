"""add contact search indexes

Revision ID: 0012_contact_search_idx
Revises: 0011_reference_field_for_ashe
Create Date: 2026-04-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "0012_contact_search_idx"
down_revision = "0011_reference_field_for_ashe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_contacts_name_trgm ON contacts USING gin (lower(name) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_contacts_email_trgm ON contacts USING gin (lower(email_address) gin_trgm_ops)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS ix_contacts_email_trgm")
    op.execute("DROP INDEX IF EXISTS ix_contacts_name_trgm")