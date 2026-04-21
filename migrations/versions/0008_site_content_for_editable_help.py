"""add site content table for editable help page

Revision ID: 0008_site_content_help
Revises: 0007_user_spellcheck_pref
Create Date: 2026-04-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0008_site_content_help"
down_revision = "0007_user_spellcheck_pref"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_content",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("site_content")
