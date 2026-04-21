"""Add per-user comment spellcheck preference.

Revision ID: 0007_user_spellcheck_pref
Revises: 0006_comment_contact_snapshots
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0007_user_spellcheck_pref"
down_revision = "0006_comment_contact_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "comment_spellcheck_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("users", "comment_spellcheck_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "comment_spellcheck_enabled")
